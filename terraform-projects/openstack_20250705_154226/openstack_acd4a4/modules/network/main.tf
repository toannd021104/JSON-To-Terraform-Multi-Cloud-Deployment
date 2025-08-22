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

# Attach subnets to routers as interfaces
resource "openstack_networking_router_interface_v2" "interface" {
  # Flatten the mapping of routers to subnets
  for_each = merge([
    for r in var.routers : {
      for net in r.networks : "${r.name}-${net.name}" => {
        router_id = openstack_networking_router_v2.router[r.name].id
        subnet_id = openstack_networking_subnet_v2.subnet[net.name].id
      }
    }
  ]...)

  router_id = each.value.router_id
  subnet_id = each.value.subnet_id
}
