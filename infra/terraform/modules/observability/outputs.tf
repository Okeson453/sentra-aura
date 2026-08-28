output "prometheus_namespace" {
  value = kubernetes_namespace.observability.metadata[0].name
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.sentra.name
}
