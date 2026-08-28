output "tenant_role_arns" {
  value = { for k, v in aws_iam_role.tenant_role : k => v.arn }
}

output "tenant_s3_policy_arns" {
  value = { for k, v in aws_iam_policy.tenant_s3 : k => v.arn }
}
