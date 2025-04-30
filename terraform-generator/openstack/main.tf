# Auto-generated Terraform configuration for OPENSTACK
terraform {
  required_version = ">= 0.14.0"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53.0"
    }
  }
}

provider "openstack" {
  auth_url    = var.openstack_auth_url
  region      = var.openstack_region
  user_name   = var.openstack_user_name
  tenant_name = var.openstack_tenant_name
  password    = var.openstack_password
  endpoint_overrides = {
    compute = "http://10.102.192.230:8774/v2.1/"  
  }
}

locals {
  topology = jsondecode(file("topology.json"))
}

module "network" {
  source = "./modules/network"

  networks           = local.topology.networks
  routers            = local.topology.routers
  external_network_id = var.external_network_id
}

module "instance" {
  source = "./modules/instance"
  
  for_each = { for inst in local.topology.instances : inst.name => inst }

  instance_name = each.value.name
  image_name    = lookup({"vm1": {"image": "Ubuntu 16", "flavor": "m2"}, "s2": {"image": "Ubuntu 16", "flavor": "m2"}}, each.key, {}).image
  flavor_name   = lookup({"vm1": {"image": "Ubuntu 16", "flavor": "m2"}, "s2": {"image": "Ubuntu 16", "flavor": "m2"}}, each.key, {}).flavor
  network_id    = module.network.network_ids[each.value.networks[0].name]
  fixed_ip      = each.value.networks[0].ip
}

output "instance_ips" {
  value = {
    for k, v in module.instance : k => v.private_ip
  }
}
