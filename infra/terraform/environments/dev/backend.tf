terraform {
  backend "s3" {
    bucket         = "sentra-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "sentra-terraform-locks"
  }
}
