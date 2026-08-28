output "cluster_endpoint" {
  value = aws_rds_cluster.sentra.endpoint
}

output "cluster_reader_endpoint" {
  value = aws_rds_cluster.sentra.reader_endpoint
}

output "cluster_port" {
  value = aws_rds_cluster.sentra.port
}

output "cluster_id" {
  value = aws_rds_cluster.sentra.id
}

output "secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "kms_key_arn" {
  value = aws_kms_key.db.arn
}
