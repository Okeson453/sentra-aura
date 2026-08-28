# ------------------------------------------------------------------------------
# SentraAura — Event Bus Module
# Implements Backend-Infrastructure-DevOps.md §3.3
# NATS JetStream deployed via Helm on EKS.
# ------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "event-bus"
    managed_by  = "terraform"
  })
}

provider "kubernetes" {
  host                   = var.cluster_endpoint
  cluster_ca_certificate = base64decode(var.cluster_ca_certificate)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", var.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = var.cluster_endpoint
    cluster_ca_certificate = base64decode(var.cluster_ca_certificate)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", var.cluster_name]
    }
  }
}

resource "kubernetes_namespace" "nats" {
  metadata {
    name = "nats"
    labels = {
      name        = "nats"
      environment = var.environment
    }
  }
}

resource "helm_release" "nats" {
  name       = "nats"
  repository = "https://nats-io.github.io/k8s/helm/charts/"
  chart      = "nats"
  version    = "1.2.0"
  namespace  = kubernetes_namespace.nats.metadata[0].name

  values = [templatefile("${path.module}/nats-values.yaml", {
    environment = var.environment
    node_pool   = var.node_pool
  })]

  depends_on = [kubernetes_namespace.nats]
}
