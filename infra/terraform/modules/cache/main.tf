# ------------------------------------------------------------------------------
# SentraAura — Cache Module
# Implements Backend-Infrastructure-DevOps.md §3.2
# ElastiCache Redis cluster, multi-AZ, encrypted.
# ------------------------------------------------------------------------------

locals {
  cluster_name = "sentra-${var.environment}"
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "cache"
    managed_by  = "terraform"
  })
}

resource "aws_elasticache_subnet_group" "sentra" {
  name       = "sentra-${var.environment}-cache-subnet"
  subnet_ids = var.subnet_ids

  tags = local.common_tags
}

resource "aws_elasticache_parameter_group" "sentra" {
  name   = "sentra-${var.environment}-redis-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "activedefrag"
    value = "yes"
  }

  tags = local.common_tags
}

resource "aws_elasticache_replication_group" "sentra" {
  replication_group_id = "sentra-${var.environment}"
  description          = "SentraAura Redis cluster for ${var.environment}"

  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.sentra.name
  subnet_group_name    = aws_elasticache_subnet_group.sentra.name
  security_group_ids   = [var.cache_security_group_id]

  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  snapshot_retention_limit = 7
  snapshot_window          = "05:00-06:00"

  apply_immediately = var.environment != "production"

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}"
  })
}
