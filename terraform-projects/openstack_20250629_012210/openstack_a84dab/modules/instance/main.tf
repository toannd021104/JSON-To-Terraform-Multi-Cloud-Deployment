terraform {
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
    }
  }
}

resource "openstack_compute_instance_v2" "instance" {
  for_each = { for inst in [var.instance_name] : inst => inst } 

  name        = var.instance_name
  image_name  = var.image_name
  flavor_name = var.flavor_name
  key_pair    = var.key_pair
  security_groups = var.security_groups
  network {
    uuid        = var.network_id
    fixed_ip_v4 = var.fixed_ip
  }
  user_data = var.user_data
}

