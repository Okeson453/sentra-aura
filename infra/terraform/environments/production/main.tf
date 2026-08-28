# ------------------------------------------------------------------------------
# SentraAura — Production Environment
# Full production stack with maximum redundancy and protection.
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

locals {
  common_tags = {
    environment = var.environment
    project     = "sentra-aura"
  }
}

module "networking" {
  source      = "../../modules/networking"
  environment = var.environment
  tags        = local.common_tags
}

module "kubernetes_cluster" {
  source             = "../../modules/kubernetes-cluster"
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids
  cluster_version    = "1.29"
  node_pools = {
    system = {
      instance_type = "t3.large"
      min_size      = 3
      max_size      = 10
      desired_size  = 4
      labels        = { "sentra.io/node-pool" = "system" }
      taints        = []
    }
    cpu-agent = {
      instance_type = "c6i.2xlarge"
      min_size      = 3
      max_size      = 20
      desired_size  = 5
      labels        = { "sentra.io/node-pool" = "cpu-agent" }
      taints        = []
    }
    gpu-render = {
      instance_type = "g4dn.2xlarge"
      min_size      = 2
      max_size      = 10
      desired_size  = 3
      labels        = { "sentra.io/node-pool" = "gpu-render" }
      taints = [{
        key    = "sentra.io/gpu-render"
        value  = "true"
        effect = "NoSchedule"
      }]
    }
    gpu-clipping = {
      instance_type = "g4dn.2xlarge"
      min_size      = 2
      max_size      = 10
      desired_size  = 3
      labels        = { "sentra.io/node-pool" = "gpu-clipping" }
      taints = [{
        key    = "sentra.io/gpu-clipping"
        value  = "true"
        effect = "NoSchedule"
      }]
    }
    data = {
      instance_type = "r6g.2xlarge"
      min_size      = 3
      max_size      = 8
      desired_size  = 4
      labels        = { "sentra.io/node-pool" = "data" }
      taints        = []
    }
  }
  tags = local.common_tags
}

module "database" {
  source                     = "../../modules/database"
  environment                = var.environment
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  instance_class             = "db.r6g.2xlarge"
  engine_version             = "16.3"
  multi_az                   = true
  backup_retention_period    = 30
  deletion_protection        = true
  tags                       = local.common_tags
}

module "cache" {
  source                  = "../../modules/cache"
  environment             = var.environment
  vpc_id                  = module.networking.vpc_id
  subnet_ids              = module.networking.private_subnet_ids
  cache_security_group_id = module.networking.cache_security_group_id
  node_type               = "cache.r6g.xlarge"
  num_cache_nodes         = 3
  tags                    = local.common_tags
}

module "object_storage" {
  source      = "../../modules/object-storage"
  environment = var.environment
  buckets = {
    media = {
      tier           = "media"
      versioning     = true
      encryption     = true
      lifecycle_days = 365
      public_access  = false
    }
    archival = {
      tier           = "archival"
      versioning     = true
      encryption     = true
      lifecycle_days = 2555
      public_access  = false
    }
    temp = {
      tier           = "temp"
      versioning     = false
      encryption     = true
      lifecycle_days = 30
      public_access  = false
    }
  }
  tags = local.common_tags
}

module "secrets" {
  source      = "../../modules/secrets"
  environment = var.environment
  secrets = {
    "control-plane-api/db"      = { description = "Control Plane API database credentials" }
    "orchestrator/temporal"     = { description = "Orchestrator Temporal credentials" }
    "agent-runtime/providers"   = { description = "Agent Runtime AI provider API keys" }
    "provider-gateway/keys"     = { description = "Provider Gateway API keys" }
    "billing-service/stripe"    = { description = "Billing Stripe credentials" }
    "notification-service/smtp" = { description = "Notification SMTP credentials" }
    "rights-registry-service/keys" = { description = "Rights Registry signing keys" }
  }
  tags = local.common_tags
}

module "event_bus" {
  source                 = "../../modules/event-bus"
  environment            = var.environment
  cluster_name           = module.kubernetes_cluster.cluster_name
  cluster_endpoint       = module.kubernetes_cluster.cluster_endpoint
  cluster_ca_certificate = module.kubernetes_cluster.cluster_certificate_authority_data
  tags                   = local.common_tags
}

module "observability" {
  source                 = "../../modules/observability"
  environment            = var.environment
  cluster_name           = module.kubernetes_cluster.cluster_name
  cluster_endpoint       = module.kubernetes_cluster.cluster_endpoint
  cluster_ca_certificate = module.kubernetes_cluster.cluster_certificate_authority_data
  vpc_id                 = module.networking.vpc_id
  tags                   = local.common_tags
}

module "dns_tls" {
  source                 = "../../modules/dns-tls"
  environment            = var.environment
  domain_name            = var.domain_name
  cluster_name           = module.kubernetes_cluster.cluster_name
  cluster_endpoint       = module.kubernetes_cluster.cluster_endpoint
  cluster_ca_certificate = module.kubernetes_cluster.cluster_certificate_authority_data
  tags                   = local.common_tags
}

module "warehouse" {
  source                     = "../../modules/warehouse"
  environment                = var.environment
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  instance_class             = "db.r6g.2xlarge"
  tags                       = local.common_tags
}

module "tenant_provisioning" {
  source                     = "../../modules/tenant-provisioning"
  environment                = var.environment
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  cache_security_group_id    = module.networking.cache_security_group_id
  tags                       = local.common_tags
}
