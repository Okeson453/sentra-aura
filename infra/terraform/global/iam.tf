# ------------------------------------------------------------------------------
# SentraAura — Global IAM
# Implements Backend-Infrastructure-DevOps.md §6.4
# Cross-account IAM roles, Terraform execution role, CI/CD roles.
# ------------------------------------------------------------------------------

locals {
  common_tags = {
    project    = "sentra-aura"
    managed_by = "terraform"
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = local.common_tags
  }
}

# Terraform execution role
resource "aws_iam_role" "terraform_execution" {
  name = "sentra-terraform-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = "sentra-terraform"
        }
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "terraform_execution" {
  name        = "sentra-terraform-execution"
  description = "Full access for Terraform state management"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TerraformState"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
        ]
        Resource = [
          "arn:aws:s3:::sentra-terraform-state",
          "arn:aws:s3:::sentra-terraform-state/*",
          "arn:aws:dynamodb:*:*:table/sentra-terraform-locks",
        ]
      },
      {
        Sid    = "TerraformResources"
        Effect = "Allow"
        Action = ["*"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = ["us-east-1", "us-west-2", "eu-west-1"]
          }
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "terraform_execution" {
  role       = aws_iam_role.terraform_execution.name
  policy_arn = aws_iam_policy.terraform_execution.arn
}

# CI/CD role for GitHub Actions
resource "aws_iam_role" "github_actions" {
  name = "sentra-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:sentra-aura/sentra-aura:*"
        }
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "github_actions" {
  name        = "sentra-github-actions"
  description = "CI/CD permissions for GitHub Actions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECR"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
        ]
        Resource = "*"
      },
      {
        Sid    = "EKS"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters",
        ]
        Resource = "*"
      },
      {
        Sid    = "S3"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = [
          "arn:aws:s3:::sentra-terraform-state/*",
          "arn:aws:s3:::sentra-artifacts-*/*",
        ]
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions.arn
}

# Read-only auditor role
resource "aws_iam_role" "auditor" {
  name = "sentra-auditor"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "auditor" {
  name        = "sentra-auditor"
  description = "Read-only access for security audits"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ReadOnly"
      Effect = "Allow"
      Action = [
        "cloudwatch:Get*",
        "cloudwatch:List*",
        "logs:Describe*",
        "logs:FilterLogEvents",
        "logs:Get*",
        "s3:Get*",
        "s3:List*",
        "ec2:Describe*",
        "eks:Describe*",
        "eks:List*",
        "rds:Describe*",
        "elasticache:Describe*",
        "iam:Get*",
        "iam:List*",
        "kms:Describe*",
        "kms:List*",
        "secretsmanager:Describe*",
        "secretsmanager:List*",
      ]
      Resource = "*"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "auditor" {
  role       = aws_iam_role.auditor.name
  policy_arn = aws_iam_policy.auditor.arn
}

data "aws_caller_identity" "current" {}
