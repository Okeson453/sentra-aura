variable "environment" {
  type = string
}

variable "secrets" {
  type = map(object({
    description = string
    kms_key_id  = optional(string)
    recovery_window = optional(number, 7)
  }))
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
