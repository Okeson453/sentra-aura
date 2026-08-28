output "secret_arns" {
  value = { for k, v in aws_secretsmanager_secret.app : k => v.arn }
}

output "kms_key_arn" {
  value = aws_kms_key.secrets.arn
}
