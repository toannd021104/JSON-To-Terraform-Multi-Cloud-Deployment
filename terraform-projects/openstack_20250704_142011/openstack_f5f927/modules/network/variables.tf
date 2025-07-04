variable "networks" {
  type = list(object({
    name = string
    cidr = string
    gateway_ip = string
    enable_dhcp = bool
    pool = list(string)
  }))
}

variable "routers" {
  type = list(object({
    name = string
    networks = list(object({
      name = string
      ip = string
    }))
    external = bool
    routes = list(object({
      cidr_block = string
      gateway_id = string
    }))
  }))
}

variable "external_network_id" {
  type = string
}