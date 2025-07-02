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


# Tạo keypair 
resource "openstack_compute_keypair_v2" "my_key" {
  name       = "toanndcloud-keypair"
  public_key = file("${path.root}/tf-cloud-init.pub")
}

