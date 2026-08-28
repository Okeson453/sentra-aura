# ------------------------------------------------------------------------------
# SentraAura — Object Storage Module
# Implements Backend-Infrastructure-DevOps.md §3.2
# S3 buckets per tier with versioning, encryption, lifecycle, access logging.
# ------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "object-storage"
    managed_by  = "terraform"
  })
}

# KMS key for S3 encryption
resource "aws_kms_key" "s3" {
  description             = "S3 encryption for sentra-${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_alias" "s3" {
  name          = "alias/sentra-${var.environment}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# Access logging bucket
resource "aws_s3_bucket" "logs" {
  bucket = "sentra-${var.environment}-access-logs"
  tags   = local.common_tags
}

resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "logs" {
  bucket = aws_s3_bucket.logs.id
  acl    = "log-delivery-write"

  depends_on = [aws_s3_bucket_ownership_controls.logs]
}

resource "aws_s3_bucket_versioning" "logs" {
  bucket = aws_s3_bucket.logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Application buckets
resource "aws_s3_bucket" "app" {
  for_each = var.buckets

  bucket = "sentra-${var.environment}-${each.key}"
  tags   = merge(local.common_tags, {
    Name = "sentra-${var.environment}-${each.key}"
    tier = each.value.tier
  })
}

resource "aws_s3_bucket_versioning" "app" {
  for_each = var.buckets

  bucket = aws_s3_bucket.app[each.key].id
  versioning_configuration {
    status = each.value.versioning ? "Enabled" : "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app" {
  for_each = { for k, v in var.buckets : k => v if v.encryption }

  bucket = aws_s3_bucket.app[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "app" {
  for_each = var.buckets

  bucket = aws_s3_bucket.app[each.key].id

  block_public_acls       = !each.value.public_access
  block_public_policy     = !each.value.public_access
  ignore_public_acls      = !each.value.public_access
  restrict_public_buckets = !each.value.public_access
}

resource "aws_s3_bucket_lifecycle_configuration" "app" {
  for_each = { for k, v in var.buckets : k => v if v.lifecycle_days > 0 }

  bucket = aws_s3_bucket.app[each.key].id

  rule {
    id     = "archive-old-versions"
    status = "Enabled"

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = each.value.lifecycle_days
    }
  }
}

resource "aws_s3_bucket_logging" "app" {
  for_each = var.buckets

  bucket = aws_s3_bucket.app[each.key].id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "${each.key}/"
}

# CORS for media buckets
resource "aws_s3_bucket_cors_configuration" "app" {
  for_each = { for k, v in var.buckets : k => v if v.tier == "media" }

  bucket = aws_s3_bucket.app[each.key].id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    max_age_seconds = 3000
  }
}
