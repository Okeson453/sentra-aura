terraform {
  backend "s3" {
    bucket         = "sentra-terraform-state-local"
    key            = "local/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "sentra-terraform-locks"
  }
}
