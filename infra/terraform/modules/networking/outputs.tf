output "vpc_id" {
  value = aws_vpc.sentra.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "inter_service_security_group_id" {
  value = aws_security_group.inter_service.id
}

output "database_security_group_id" {
  value = aws_security_group.database.id
}

output "cache_security_group_id" {
  value = aws_security_group.cache.id
}

output "vpc_cidr" {
  value = aws_vpc.sentra.cidr_block
}
