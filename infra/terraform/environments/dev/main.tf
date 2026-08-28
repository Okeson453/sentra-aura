# ------------------------------------------------------------------------------
# SentraAura — Dev Environment
# Full stack with reduced instance sizes for cost control.
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
  source = "../../modules/networking"
  environment = var.environment
  tags = local.common_tags
}

module "kubernetes_cluster" {
  source = "../../modules/kubernetes-cluster"
  environment = var.environment
  vpc_id = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids = module.networking.public_subnet_ids
  node_pools = {
    system = {
      instance_type = "t3.medium"
      min_size      = 2
      max_size      = 4
      desired_size  = 2
      labels = { "sentra.io/node-pool" = "system" }
      taints = []
    }
    cpu-agent = {
      instance_type = "t3.large"
      min_size      = 1
      max_size      = 3
      desired_size  = 1
      labels = { "sentra.io/node-pool" = "cpu-agent" }
      taints = []
    }
    gpu-render = {
      instance_type = "g4dn.xlarge"
      min_size      = 0
      max_size      = 2
      desired_size  = 0
      labels = { "sentra.io/node-pool" = "gpu-render" }
      taints = [{
        key    = "sentra.io/gpu-render"
        value  = "true"
        effect = "NoSchedule"
      }]
    }
    gpu-clipping = {
      instance_type = "g4dn.xlarge"
      min_size      = 0
      max_size      = 2
      desired_size  = 0
      labels = { "sentra.io/node-pool" = "gpu-clipping" }
      taints = [{
        key    = "sentra.io/gpu-clipping"
        value  = "true"
        effect = "NoSchedule"
      }]
    }
    data = {
      instance_type = "t3.large"
      min_size      = 1
      max_size      = 2
      desired_size  = 1
      labels = { "sentra.io/node-pool" = "data" }
      taints = []
    }
  }
  tags = local.common_tags
}

module "database" {
  source = "../../modules/database"
  environment = var.environment
  vpc_id = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  instance_class = "db.r6g.large"
  multi_az = false
  deletion_protection = false
  tags = local.common_tags
}

module "cache" {
  source = "../../modules/cache"
  environment = var.environment
  vpc_id = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids
  cache_security_group_id = module.networking.cache_security_group_id
  node_type = "cache.t4g.medium"
  num_cache_nodes = 1
  tags = local.common_tags
}

module "object_storage" {
  source = "../../modules/object-storage"
  environment = var.environment
  buckets = {
    media = {
      tier           = "media"
      versioning     = true
      encryption     = true
      lifecycle_days = 30
      public_access  = false
    }
    archival = {
      tier           = "archival"
      versioning     = true
      encryption     = true
      lifecycle_days = 90
      public_access  = false
    }
    temp = {
      tier           = "temp"
      versioning     = false
      encryption     = true
      lifecycle_days = 7
      public_access  = false
    }
  }
  tags = local.common_tags
}

module "secrets" {
  source = "../../modules/secrets"
  environment = var.environment
  secrets = {
    "control-plane-api/db" = {
      description = "Control Plane API database credentials"
    }
    "orchestrator/temporal" = {
      description = "Orchestrator Temporal credentials"
    }
    "agent-runtime/providers" = {
      description = "Agent Runtime AI provider API keys"
    }
  }
  tags = local.common_tags
}

module "event_bus" {
  source = "../../modules/event-bus"
  environment = var.environment
  cluster_name = module.kubernetes_cluster.cluster_name
  cluster_endpoint = module.kubernetes_cluster.cluster_endpoint
  cluster_ca_certificate = module.kubernetes_cluster.cluster_certificate_authority_data
  tags = local.common_tags
}

module "observability" {
  source = "../../modules/observability"
  environment = var.environment
  cluster_name = module.kubernetes_cluster.cluster_name
  cluster_endpoint = module.kubernetes_cluster.cluster_endpoint
  cluster_ca_certificate = module.kubernetes_cluster.cluster_certificate_authority_data
  vpc_id = module.networking.vpc_id
  tags = local.common_tags
}

module "dns_tls" {
  source = "../../modules/dns-tls"
  environment = var.environment
  domain_name = var.domain_name
  cluster_name = module.kubernetes_cluster.cluster_name
  cluster_endpoint = module.kubernetes_cluster.cluster_endpoint
  cluster_ca_certificate = module.kubernetes_cluster.cluster_certificate_authority_data
  tags = local.common_tags
}

module "warehouse" {
  source = "../../modules/warehouse"
  environment = var.environment
  vpc_id = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  instance_class = "db.r6g.large"
  tags = local.common_tags
}

module "tenant_provisioning" {
  source = "../../modules/tenant-provisioning"
  environment = var.environment
  vpc_id = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  cache_security_group_id = module.networking.cache_security_group_id
  tags = local.common_tags
}
