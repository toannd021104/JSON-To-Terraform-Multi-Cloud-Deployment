
terraform {
  required_version = ">= 0.14.0"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53.0"
    }
  }
}


# Configure the OpenStack provider using variables
provider "openstack" {
  auth_url    = var.openstack_auth_url
  region      = var.openstack_region
  user_name   = var.openstack_user_name
  tenant_name = var.openstack_tenant_name
  password    = var.openstack_password
  # Override default compute endpoint if needed
  endpoint_overrides = {
    compute = "http://10.102.192.230:8774/v2.1/"
  }
}


# ========================================
# Load topology data from a JSON file
# ========================================
locals {
  topology = jsondecode(file("${path.root}/topology.json"))
}


# ========================================
# Network Module
# Creates networks and routers as defined in topology
# ========================================
module "network" {
  source              = "./modules/network"
  networks            = local.topology.networks
  routers             = local.topology.routers
  external_network_id = "c668f27f-c14b-410d-b1df-016adc280c6e"  # External (public) network ID
}


# ========================================
# Instance Module
# Deploys VMs based on the topology file
# ========================================
module "instance" {
  depends_on = [module.network]  # Ensure networking is provisioned first
  source     = "./modules/instance"
  # Loop through each instance defined in the topology file
  for_each = { for inst in local.topology.instances : inst.name => inst }
  instance_name = each.value.name
  # Assign image and flavor for each instance
  image_name  = lookup({"master_f5f927": {"image": "ubuntu-jammy", "flavor": "m2"}, "worker1_f5f927": {"image": "ubuntu-jammy", "flavor": "m2"}}, each.key, {}).image
  flavor_name = lookup({"master_f5f927": {"image": "ubuntu-jammy", "flavor": "m2"}, "worker1_f5f927": {"image": "ubuntu-jammy", "flavor": "m2"}}, each.key, {}).flavor
  # Assign network and fixed IP to the instance
  network_id = module.network.network_ids[each.value.networks[0].name]
  fixed_ip   = each.value.networks[0].ip
  # Use cloud-init script if defined
  user_data = each.value.cloud_init != null ? file("${path.root}/cloud_init/${each.value.cloud_init}") : null
  # Configure SSH keypair and security groups (optional)
  key_pair        = lookup(each.value, "keypair", null)
  security_groups = lookup(each.value, "security_groups", ["default"])
  # Assign floating IP if provided
  floating_ip_address = lookup(each.value, "floating_ip", null)
}
