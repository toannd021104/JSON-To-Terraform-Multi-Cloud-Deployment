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

resource "openstack_compute_keypair_v2" "my_key" {
  name       = "toanndcloud-keypair"
  public_key = file("${path.root}/tf-cloud-init.pub")
}

resource "openstack_compute_instance_v2" "bastion" {
  name        = "bastion-host"
  image_name  = "ubuntu-jammy"
  flavor_name = "m2"
  key_pair    = openstack_compute_keypair_v2.my_key.name
  security_groups = ["default"]

  network {
    name = "public-network"
  }
}

module "network" {
  source              = "./modules/network"
  networks            = local.topology.networks
  routers             = local.topology.routers
  external_network_id = var.external_network_id
}

module "instance" {
  depends_on   = [module.network]
  source       = "./modules/instance"
  for_each     = { for inst in local.topology.instances : inst.name => inst }
  instance_name = each.value.name
  image_name    = lookup({"vm1_a84dab": {"image": "ubuntu-jammy", "flavor": "m2"}, "s2_a84dab": {"image": "ubuntu-jammy", "flavor": "m2"}}, each.key, {}).image
  flavor_name   = lookup({"vm1_a84dab": {"image": "ubuntu-jammy", "flavor": "m2"}, "s2_a84dab": {"image": "ubuntu-jammy", "flavor": "m2"}}, each.key, {}).flavor
  network_id    = module.network.network_ids[each.value.networks[0].name]
  fixed_ip      = each.value.networks[0].ip
  user_data     = each.value.cloud_init != null ? file("${path.module}/cloud_init/${each.value.cloud_init}") : null
  key_pair      = openstack_compute_keypair_v2.my_key.name
  security_groups = ["default"] 
}
