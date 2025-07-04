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
    pool        = list(string)
    gateway_ip  = string
    enable_dhcp = bool
  }))
}

variable "availability_zones" {
  type = list(string)
}

variable "routers" {
  type = list(object({
    name     = string
    networks = list(object({
      name = string
      ip   = string
    }))
    external = bool
    routes   = list(object({
      cidr_block = string
      gateway_id = string
    }))
  }))
}