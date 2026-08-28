# ------------------------------------------------------------------------------
# SentraAura — Local Environment
# Lightweight setup for local development with docker-compose parity.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      environment = var.environment
      managed_by  = "terraform"
    }
  }
}

# Local environment uses docker-compose; this file defines minimal AWS resources
# for localstack compatibility or lightweight AWS sandbox.

resource "aws_s3_bucket" "local_media" {
  bucket = "sentra-local-media"
}

resource "aws_s3_bucket_versioning" "local_media" {
  bucket = aws_s3_bucket.local_media.id
  versioning_configuration {
    status = "Enabled"
  }
}
