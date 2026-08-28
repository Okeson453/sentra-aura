terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }

  backend "s3" {
    bucket         = "sentra-terraform-state"
    key            = "global/iam.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "sentra-terraform-locks"
  }
}
