variable "environment" {
  type = string
}

variable "service_roles" {
  type = map(string)
  default = {}
}

variable "secret_arns" {
  type = map(string)
  default = {}
}
