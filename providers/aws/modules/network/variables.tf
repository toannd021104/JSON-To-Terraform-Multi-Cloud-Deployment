variable "vpc_cidr_block" {
  type = string
}

variable "public_subnet_cidrs" {
  type = list(string)
}

variable "private_subnets" {
  type = list(object({
    name        = string
    cidr        = string
    pool        = optional(list(string), [])
    gateway_ip  = optional(string, null)
    enable_dhcp = bool
  }))
}

variable "availability_zones" {
  type = list(string)
}

variable "routers" {
  type = list(object({
    name     = string
    networks = optional(list(object({
      name = string
      ip   = string
    })), [])
    external = bool
    routes   = optional(list(object({
      cidr_block = string
      gateway_id = string
    })), [])
  }))
}