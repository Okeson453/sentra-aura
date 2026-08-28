output "hosted_zone_id" {
  value = aws_route53_zone.sentra.zone_id
}

output "acm_certificate_arn" {
  value = aws_acm_certificate.sentra.arn
}

output "domain_name" {
  value = var.domain_name
}
