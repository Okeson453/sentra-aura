output "primary_endpoint" {
  value = aws_elasticache_replication_group.sentra.primary_endpoint_address
}

output "reader_endpoint" {
  value = aws_elasticache_replication_group.sentra.reader_endpoint_address
}

output "port" {
  value = aws_elasticache_replication_group.sentra.port
}

output "replication_group_id" {
  value = aws_elasticache_replication_group.sentra.id
}
