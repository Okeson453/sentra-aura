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

variable "instance_class" {
  type    = string
  default = "db.r6g.large"
}

variable "tags" {
  type    = map(string)
  default = {}
}
