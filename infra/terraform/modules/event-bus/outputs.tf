output "nats_namespace" {
  value = kubernetes_namespace.nats.metadata[0].name
}

output "nats_service" {
  value = "nats.nats.svc.cluster.local"
}
