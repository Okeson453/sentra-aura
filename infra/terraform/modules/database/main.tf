# ------------------------------------------------------------------------------
# SentraAura — Database Module
# Implements Backend-Infrastructure-DevOps.md §3.2
# Aurora PostgreSQL cluster, multi-AZ, encrypted, parameter groups.
# ------------------------------------------------------------------------------

locals {
  cluster_name = "sentra-${var.environment}"
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "database"
    managed_by  = "terraform"
  })
}

# DB subnet group
resource "aws_db_subnet_group" "sentra" {
  name       = "sentra-${var.environment}-db-subnet"
  subnet_ids = var.subnet_ids

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-db-subnet"
  })
}

# DB parameter group
resource "aws_rds_cluster_parameter_group" "sentra" {
  name        = "sentra-${var.environment}-pg"
  family      = "aurora-postgresql16"
  description = "SentraAura ${var.environment} parameter group"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "ssl"
    value = "1"
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = local.common_tags
}

# KMS key for DB encryption
resource "aws_kms_key" "db" {
  description             = "Database encryption for ${local.cluster_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_alias" "db" {
  name          = "alias/sentra-${var.environment}-db"
  target_key_id = aws_kms_key.db.key_id
}

# Aurora cluster
resource "aws_rds_cluster" "sentra" {
  cluster_identifier        = "sentra-${var.environment}"
  engine                    = "aurora-postgresql"
  engine_version            = var.engine_version
  engine_mode               = "provisioned"
  database_name             = "sentra"
  master_username           = "sentra_admin"
  master_password           = random_password.db.result
  db_subnet_group_name      = aws_db_subnet_group.sentra.name
  vpc_security_group_ids    = [var.database_security_group_id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.sentra.name
  backup_retention_period   = var.backup_retention_period
  preferred_backup_window   = "03:00-04:00"
  deletion_protection       = var.deletion_protection
  storage_encrypted         = true
  kms_key_id                = aws_kms_key.db.arn
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "sentra-${var.environment}-final" : null
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}"
  })
}

# Writer instance
resource "aws_rds_cluster_instance" "writer" {
  identifier         = "sentra-${var.environment}-writer"
  cluster_identifier = aws_rds_cluster.sentra.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.sentra.engine

  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.db.arn
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-writer"
  })
}

# Reader instances (multi-AZ)
resource "aws_rds_cluster_instance" "reader" {
  count              = var.multi_az ? 2 : 0
  identifier         = "sentra-${var.environment}-reader-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.sentra.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.sentra.engine

  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.db.arn
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-reader-${count.index + 1}"
  })
}

# Random password
resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Secrets Manager for DB credentials
resource "aws_secretsmanager_secret" "db" {
  name                    = "sentra-${var.environment}/database/master"
  description             = "Master credentials for Aurora PostgreSQL"
  kms_key_id              = aws_kms_key.db.arn
  recovery_window_in_days = 7
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = aws_rds_cluster.sentra.master_username
    password = random_password.db.result
    host     = aws_rds_cluster.sentra.endpoint
    port     = 5432
    dbname   = aws_rds_cluster.sentra.database_name
  })
}

# IAM role for RDS monitoring
resource "aws_iam_role" "rds_monitoring" {
  name = "sentra-${var.environment}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
