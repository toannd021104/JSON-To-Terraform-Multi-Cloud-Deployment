terraform {
  required_providers {
    openstack = {
      source = "terraform-provider-openstack/openstack"
    }
  }
}

# Create OpenStack networks
resource "openstack_networking_network_v2" "network" {
  for_each       = { for net in var.networks : net.name => net }
  name           = each.value.name               # Network name
  admin_state_up = true                          # Enable network
}

# Create subnets for each network
resource "openstack_networking_subnet_v2" "subnet" {
  for_each     = { for net in var.networks : net.name => net }
  network_id   = openstack_networking_network_v2.network[each.key].id
  cidr         = each.value.cidr                 # Subnet CIDR
  gateway_ip   = each.value.gateway_ip           # Gateway IP
  enable_dhcp  = each.value.enable_dhcp          # Enable DHCP
}

# Create routers (with optional external network)
resource "openstack_networking_router_v2" "router" {
  for_each            = { for r in var.routers : r.name => r }
  name                = each.value.name                  # Router name
  admin_state_up      = true                             # Enable router
  external_network_id = each.value.external ? var.external_network_id : null
}

# Create ports for router interfaces with specific IPs
resource "openstack_networking_port_v2" "router_port" {
  for_each = merge([
    for r in var.routers : {
      for net in r.networks : "${r.name}-${net.name}" => {
        network_id = openstack_networking_network_v2.network[net.name].id
        subnet_id  = openstack_networking_subnet_v2.subnet[net.name].id
        ip_address = net.ip
        router_name = r.name
      }
    }
  ]...)

  name           = "port-${each.key}"
  network_id     = each.value.network_id
  admin_state_up = true

  fixed_ip {
    subnet_id  = each.value.subnet_id
    ip_address = each.value.ip_address
  }
}

# Attach ports to routers as interfaces
resource "openstack_networking_router_interface_v2" "interface" {
  for_each = merge([
    for r in var.routers : {
      for net in r.networks : "${r.name}-${net.name}" => {
        router_id = openstack_networking_router_v2.router[r.name].id
        port_id   = openstack_networking_port_v2.router_port["${r.name}-${net.name}"].id
      }
    }
  ]...)

  router_id = each.value.router_id
  port_id   = each.value.port_id
}

# Create static routes for routers
resource "openstack_networking_router_route_v2" "route" {
  # Flatten routes from all routers into a single map
  for_each = merge([
    for r in var.routers : {
      for idx, route in coalesce(r.routes, []) : "${r.name}-route-${idx}" => {
        router_id        = openstack_networking_router_v2.router[r.name].id
        destination_cidr = route.destination
        next_hop         = route.nexthop
      }
    }
  ]...)

  depends_on = [openstack_networking_router_interface_v2.interface]

  router_id        = each.value.router_id
  destination_cidr = each.value.destination_cidr
  next_hop         = each.value.next_hop
}
