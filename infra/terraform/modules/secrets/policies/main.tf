# ------------------------------------------------------------------------------
# SentraAura — Secrets Policies Sub-module
# IAM policies attaching specific secrets to specific service roles.
# ------------------------------------------------------------------------------

locals {
  common_tags = {
    environment = var.environment
    service     = "secrets-policies"
    managed_by  = "terraform"
  }
}

resource "aws_iam_policy" "secret_access" {
  for_each = var.service_roles

  name        = "sentra-${var.environment}-${each.key}-secrets-access"
  description = "Allow ${each.key} to access its secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetSecretValue"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = [
          for secret_name, secret_arn in var.secret_arns :
          secret_arn if startswith(secret_name, each.key)
        ]
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "secret_access" {
  for_each = var.service_roles

  role       = each.value
  policy_arn = aws_iam_policy.secret_access[each.key].arn
}
