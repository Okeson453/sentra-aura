# SentraAura — Terraform Infrastructure

## Overview

This directory contains all Infrastructure-as-Code (IaC) for the SentraAura platform, organized into modules, environments, and global resources.

## Directory Structure

```
terraform/
├── modules/              # Reusable Terraform modules
│   ├── kubernetes-cluster/   # EKS cluster with multi-pool node groups
│   ├── networking/           # VPC, subnets, security groups
│   ├── database/             # Aurora PostgreSQL
│   ├── cache/                # ElastiCache Redis
│   ├── event-bus/            # NATS JetStream on EKS
│   ├── object-storage/       # S3 buckets with lifecycle policies
│   ├── secrets/              # AWS Secrets Manager + IAM policies
│   ├── observability/        # Prometheus, Grafana, Loki
│   ├── dns-tls/              # Route53, cert-manager
│   ├── warehouse/            # Analytics warehouse
│   └── tenant-provisioning/  # Per-tenant IAM and resources
├── environments/         # Environment-specific configurations
│   ├── local/            # Local development (minimal)
│   ├── dev/              # Development environment
│   ├── staging/          # Staging environment
│   ├── canary/           # Canary environment for progressive rollout
│   └── production/       # Production environment
└── global/               # Cross-account global resources
    ├── iam.tf            # IAM roles (Terraform execution, CI/CD, auditor)
    └── org_policies.tf   # AWS Organization SCPs
```

## Prerequisites

- Terraform >= 1.9.0
- AWS CLI configured with appropriate credentials
- kubectl configured for EKS access
- Helm 3.15+

## Usage

### Initialize an Environment

```bash
cd terraform/environments/dev
terraform init
```

### Plan Changes

```bash
terraform plan -out=tfplan
```

### Apply Changes

```bash
terraform apply tfplan
```

### Destroy (Non-Production Only)

```bash
terraform destroy
```

## State Management

Terraform state is stored in S3 with DynamoDB locking:

- **Bucket**: `sentra-terraform-state`
- **Lock Table**: `sentra-terraform-locks`
- **Encryption**: AES-256 with KMS

## Module Usage

### Kubernetes Cluster

```hcl
module "kubernetes_cluster" {
  source             = "../../modules/kubernetes-cluster"
  environment        = "dev"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  node_pools = {
    system = {
      instance_type = "t3.medium"
      min_size      = 2
      max_size      = 4
      labels        = { "sentra.io/node-pool" = "system" }
    }
  }
}
```

### Database

```hcl
module "database" {
  source                     = "../../modules/database"
  environment                = "dev"
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  instance_class             = "db.r6g.large"
}
```

## Security

- All secrets encrypted with AWS KMS
- VPC flow logs enabled
- Default security group denies all traffic
- Inter-service communication restricted to VPC CIDR
- Terraform execution role follows least privilege

## Cost Control

- Auto-scaling node groups with minimum sizes
- S3 lifecycle policies for archival
- RDS deletion protection in production only
- Development environments use smaller instance types
