variable "networks" {
  type = list(object({
    name = string
    cidr = string
    gateway_ip = string
    enable_dhcp = bool
  }))
}

variable "routers" {
  description = "List of routers with their network connections and static routes"
  type = list(object({
    name = string
    networks = list(object({
      name = string
      ip   = string
    }))
    external = bool
    routes = optional(list(object({
      destination = string  # CIDR block (e.g., "0.0.0.0/0" for default route)
      nexthop     = string  # Next hop IP address
    })), [])
  }))
}

variable "external_network_id" {
  type = string
}