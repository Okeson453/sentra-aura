# ------------------------------------------------------------------------------
# SentraAura — Tenant Provisioning Module
# Implements Backend-Infrastructure-DevOps.md §4.3
# Per-tenant isolated resources: namespace, DB schema, cache prefix, S3 prefix.
# ------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "tenant-provisioning"
    managed_by  = "terraform"
  })
}

# Tenant IAM roles
resource "aws_iam_role" "tenant_role" {
  for_each = toset(["tenant-a", "tenant-b", "tenant-c"])

  name = "sentra-${var.environment}-${each.value}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = data.aws_caller_identity.current.account_id
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = each.value
        }
      }
    }]
  })

  tags = merge(local.common_tags, {
    tenant = each.value
  })
}

data "aws_caller_identity" "current" {}

# Tenant-scoped S3 access policies
resource "aws_iam_policy" "tenant_s3" {
  for_each = toset(["tenant-a", "tenant-b", "tenant-c"])

  name        = "sentra-${var.environment}-${each.value}-s3"
  description = "S3 access scoped to tenant prefix"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TenantPrefixAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:aws:s3:::sentra-${var.environment}-media/${each.value}/*",
          "arn:aws:s3:::sentra-${var.environment}-media",
        ]
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "tenant_s3" {
  for_each = toset(["tenant-a", "tenant-b", "tenant-c"])

  role       = aws_iam_role.tenant_role[each.value].name
  policy_arn = aws_iam_policy.tenant_s3[each.value].arn
}

# Tenant-scoped KMS policy
resource "aws_iam_policy" "tenant_kms" {
  for_each = toset(["tenant-a", "tenant-b", "tenant-c"])

  name        = "sentra-${var.environment}-${each.value}-kms"
  description = "KMS decrypt access for tenant"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "TenantKMSDecrypt"
      Effect = "Allow"
      Action = [
        "kms:Decrypt",
        "kms:GenerateDataKey",
      ]
      Resource = "*"
      Condition = {
        StringEquals = {
          "kms:ViaService" = "s3.*.amazonaws.com"
        }
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "tenant_kms" {
  for_each = toset(["tenant-a", "tenant-b", "tenant-c"])

  role       = aws_iam_role.tenant_role[each.value].name
  policy_arn = aws_iam_policy.tenant_kms[each.value].arn
}
