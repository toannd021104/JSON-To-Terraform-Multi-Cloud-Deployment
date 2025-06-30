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
  topology = jsondecode(file("${path.root}/topology.json"))
}

# Tạo keypair giống AWS
resource "openstack_compute_keypair_v2" "my_key" {
  name       = "toanndcloud-keypair"
  public_key = file("${path.root}/tf-cloud-init.pub")
}

# # Tạo security group cho phép SSH
# resource "openstack_networking_secgroup_v2" "ssh_access" {
#   name        = "allow_ssh_access"
#   description = "Allow SSH inbound traffic"
# }

# resource "openstack_networking_secgroup_rule_v2" "ssh_access_ingress" {
#   direction         = "ingress"
#   ethertype         = "IPv4"
#   remote_ip_prefix  = "0.0.0.0/0"
#   security_group_id = openstack_networking_secgroup_v2.ssh_access.id
# }

# resource "openstack_networking_secgroup_rule_v2" "ssh_access_egress" {
#   direction         = "egress"
#   ethertype         = "IPv4"
#   remote_ip_prefix  = "0.0.0.0/0"
#   security_group_id = openstack_networking_secgroup_v2.ssh_access.id
# }

# Module mạng (network, subnet, router, router interface)
module "network" {
  source = "./modules/network"

  networks           = local.topology.networks
  routers            = local.topology.routers
  external_network_id = "c668f27f-c14b-410d-b1df-016adc280c6e" # ID của public network 
}

# Module instance, tạo các VM theo topology
module "instance" {
  source = "./modules/instance"

  for_each = { for inst in local.topology.instances : inst.name => inst }

  instance_name = each.value.name
  image_name    = lookup(
                    {
                      "vm1" = { image = "ubuntu-jammy", flavor = "m2" },
                      "s2"  = { image = "ubuntu-jammy", flavor = "m2" }
                    },
                    each.key,
                    {}
                  ).image
  flavor_name   = lookup(
                    {
                      "vm1" = { image = "ubuntu-jammy", flavor = "m2" },
                      "s2"  = { image = "ubuntu-jammy", flavor = "m2" }
                    },
                    each.key,
                    {}
                  ).flavor
  network_id    = module.network.network_ids[each.value.networks[0].name]
  fixed_ip      = each.value.networks[0].ip
  user_data     = each.value.cloud_init != null ? file("${path.root}/cloud_init/${each.value.cloud_init}") : null
  key_pair      = openstack_compute_keypair_v2.my_key.name
  security_groups = ["default"] 
}

# Tạo bastion host riêng biệt (nếu cần)
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
