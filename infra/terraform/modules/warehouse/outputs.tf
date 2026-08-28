output "cluster_endpoint" {
  value = aws_rds_cluster.warehouse.endpoint
}

output "cluster_id" {
  value = aws_rds_cluster.warehouse.id
}

output "secret_arn" {
  value = aws_secretsmanager_secret.warehouse.arn
}
