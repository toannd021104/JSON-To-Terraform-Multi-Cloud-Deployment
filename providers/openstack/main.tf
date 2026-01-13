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
    compute = "http://10.105.196.95:8774/v2.1/"
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
  external_network_id = var.external_network_id  # External network ID from variables
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
  image_name  = lookup({
    vm1 = { image = "ubuntu-jammy", flavor = "m2" },
    s2  = { image = "ubuntu-jammy", flavor = "m2" }
  }, each.key, {}).image

  flavor_name = lookup({
    vm1 = { image = "ubuntu-jammy", flavor = "m2" },
    s2  = { image = "ubuntu-jammy", flavor = "m2" }
  }, each.key, {}).flavor

  # Assign network and fixed IP to the instance
  network_id = module.network.network_ids[each.value.networks[0].name]
  fixed_ip   = each.value.networks[0].ip

  # Use cloud-init script if defined
  user_data = each.value.cloud_init != null ? file("${path.root}/cloud_init/${each.value.cloud_init}") : null

  # Configure SSH keypair and security groups (optional)
  key_pair        = lookup(each.value, "keypair", null)
  security_groups = lookup(each.value, "security_groups", ["default"])

  # Floating IP configuration:
  # - true: allocate a new floating IP
  # - false/null: no floating IP
  # - "x.x.x.x": use specific floating IP address
  floating_ip_enabled = lookup(each.value, "floating_ip", false) == true
  floating_ip_address = (
    lookup(each.value, "floating_ip", null) != null &&
    lookup(each.value, "floating_ip", null) != true &&
    lookup(each.value, "floating_ip", null) != false
  ) ? each.value.floating_ip : null

  # External network name for floating IP allocation
  # Priority: instance.floating_ip_pool > var.external_network_name
  external_network_name = lookup(each.value, "floating_ip_pool", var.external_network_name)
}
