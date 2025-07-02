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

# Load topology from JSON file
locals {
  topology = jsondecode(file("${path.root}/topology.json"))
}

# ============================
# Network Module
# ============================
module "network" {
  source             = "./modules/network"
  networks           = local.topology.networks
  routers            = local.topology.routers
  external_network_id = "c668f27f-c14b-410d-b1df-016adc280c6e"  # Public network ID
}
# ============================
# Instance Module
# ============================
module "instance" {
  depends_on = [module.network]
  source = "./modules/instance"

  for_each = { for inst in local.topology.instances : inst.name => inst }

  instance_name = each.value.name
  # Lookup image & flavor
  image_name       = lookup({
    vm1 = { image = "ubuntu-jammy", flavor = "m2" },
    s2  = { image = "ubuntu-jammy", flavor = "m2" }
  }, each.key, {}).image

  flavor_name      = lookup({
    vm1 = { image = "ubuntu-jammy", flavor = "m2" },
    s2  = { image = "ubuntu-jammy", flavor = "m2" }
  }, each.key, {}).flavor
  
  network_id       = module.network.network_ids[each.value.networks[0].name]
  fixed_ip         = each.value.networks[0].ip
  
  # Optional cloud-init script
  user_data     = each.value.cloud_init != null ? file("${path.root}/cloud_init/${each.value.cloud_init}") : null
  
  # Optional keypair and security groups
  key_pair   = lookup(each.value, "keypair", null)  
  security_groups = lookup(each.value, "security_groups", ["default"]) 
  floating_ip_address = lookup(each.value, "floating_ip", null)
}

