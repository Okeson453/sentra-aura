variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "database_security_group_id" {
  type = string
}

variable "cache_security_group_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
