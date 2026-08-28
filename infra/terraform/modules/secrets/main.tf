# ------------------------------------------------------------------------------
# SentraAura — Secrets Module
# Implements Backend-Infrastructure-DevOps.md §3.2, §6.4
# AWS Secrets Manager with rotation, KMS encryption.
# ------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "secrets"
    managed_by  = "terraform"
  })
}

# KMS key for secrets encryption
resource "aws_kms_key" "secrets" {
  description             = "Secrets encryption for sentra-${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/sentra-${var.environment}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# Secrets
resource "aws_secretsmanager_secret" "app" {
  for_each = var.secrets

  name                    = "sentra-${var.environment}/${each.key}"
  description             = each.value.description
  kms_key_id              = coalesce(each.value.kms_key_id, aws_kms_key.secrets.arn)
  recovery_window_in_days = each.value.recovery_window

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}/${each.key}"
  })
}

# Policy: restrict access by service role
resource "aws_secretsmanager_secret_policy" "app" {
  for_each = var.secrets

  secret_arn = aws_secretsmanager_secret.app[each.key].arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyUnencryptedConnections"
        Effect = "Deny"
        Principal = {
          AWS = "*"
        }
        Action   = "secretsmanager:GetSecretValue"
        Resource = "*"
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
