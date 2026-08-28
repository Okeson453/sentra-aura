# ------------------------------------------------------------------------------
# SentraAura — Observability Module
# Implements Backend-Infrastructure-DevOps.md §3.4
# Prometheus + Grafana + Loki on EKS.
# ------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "observability"
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

resource "kubernetes_namespace" "observability" {
  metadata {
    name = "observability"
    labels = {
      name        = "observability"
      environment = var.environment
    }
  }
}

# Prometheus
resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "58.0.0"
  namespace  = kubernetes_namespace.observability.metadata[0].name

  values = [templatefile("${path.module}/prometheus-values.yaml", {
    environment = var.environment
  })]

  depends_on = [kubernetes_namespace.observability]
}

# Loki
resource "helm_release" "loki" {
  name       = "loki"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  version    = "2.10.0"
  namespace  = kubernetes_namespace.observability.metadata[0].name

  values = [templatefile("${path.module}/loki-values.yaml", {
    environment = var.environment
  })]

  depends_on = [kubernetes_namespace.observability]
}

# CloudWatch log group for central aggregation
resource "aws_cloudwatch_log_group" "sentra" {
  name              = "/sentra/${var.environment}"
  retention_in_days = var.environment == "production" ? 30 : 7
  tags              = local.common_tags
}
