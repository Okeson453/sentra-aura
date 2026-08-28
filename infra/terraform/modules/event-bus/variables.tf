variable "environment" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "cluster_endpoint" {
  type = string
}

variable "cluster_ca_certificate" {
  type = string
}

variable "node_pool" {
  type = string
  default = "system"
}

variable "tags" {
  type    = map(string)
  default = {}
}
