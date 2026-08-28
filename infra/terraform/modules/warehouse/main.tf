# ------------------------------------------------------------------------------
# SentraAura — Warehouse Module
# Implements Backend-Infrastructure-DevOps.md §3.2
# Analytics warehouse (Aurora PostgreSQL or Snowflake-ready).
# ------------------------------------------------------------------------------

locals {
  warehouse_name = "sentra-${var.environment}-warehouse"
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "warehouse"
    managed_by  = "terraform"
  })
}

resource "aws_db_subnet_group" "warehouse" {
  name       = "${local.warehouse_name}-subnet"
  subnet_ids = var.subnet_ids

  tags = local.common_tags
}

resource "aws_kms_key" "warehouse" {
  description             = "Warehouse encryption for ${local.warehouse_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_alias" "warehouse" {
  name          = "alias/${local.warehouse_name}"
  target_key_id = aws_kms_key.warehouse.key_id
}

resource "aws_rds_cluster" "warehouse" {
  cluster_identifier     = local.warehouse_name
  engine                 = "aurora-postgresql"
  engine_version         = "16.3"
  engine_mode            = "provisioned"
  database_name          = "sentra_warehouse"
  master_username        = "warehouse_admin"
  master_password        = random_password.warehouse.result
  db_subnet_group_name   = aws_db_subnet_group.warehouse.name
  vpc_security_group_ids = [var.database_security_group_id]
  backup_retention_period = 7
  preferred_backup_window = "04:00-05:00"
  deletion_protection     = var.environment == "production"
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.warehouse.arn
  skip_final_snapshot     = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${local.warehouse_name}-final" : null

  tags = merge(local.common_tags, {
    Name = local.warehouse_name
  })
}

resource "aws_rds_cluster_instance" "warehouse_writer" {
  identifier         = "${local.warehouse_name}-writer"
  cluster_identifier = aws_rds_cluster.warehouse.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.warehouse.engine

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_monitoring.arn

  tags = merge(local.common_tags, {
    Name = "${local.warehouse_name}-writer"
  })
}

resource "random_password" "warehouse" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "warehouse" {
  name                    = "sentra-${var.environment}/warehouse/master"
  description             = "Master credentials for analytics warehouse"
  kms_key_id              = aws_kms_key.warehouse.arn
  recovery_window_in_days = 7
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "warehouse" {
  secret_id = aws_secretsmanager_secret.warehouse.id
  secret_string = jsonencode({
    username = aws_rds_cluster.warehouse.master_username
    password = random_password.warehouse.result
    host     = aws_rds_cluster.warehouse.endpoint
    port     = 5432
    dbname   = aws_rds_cluster.warehouse.database_name
  })
}

resource "aws_iam_role" "rds_monitoring" {
  name = "${local.warehouse_name}-monitoring"

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
