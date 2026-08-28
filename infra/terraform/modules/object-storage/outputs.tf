output "bucket_names" {
  value = { for k, v in aws_s3_bucket.app : k => v.id }
}

output "bucket_arns" {
  value = { for k, v in aws_s3_bucket.app : k => v.arn }
}

output "kms_key_arn" {
  value = aws_kms_key.s3.arn
}
