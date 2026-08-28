output "policy_arns" {
  value = { for k, v in aws_iam_policy.secret_access : k => v.arn }
}
