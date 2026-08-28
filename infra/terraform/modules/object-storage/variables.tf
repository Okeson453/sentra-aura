variable "environment" {
  type = string
}

variable "buckets" {
  type = map(object({
    tier           = string
    versioning     = bool
    encryption     = bool
    lifecycle_days = number
    public_access  = bool
  }))
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
