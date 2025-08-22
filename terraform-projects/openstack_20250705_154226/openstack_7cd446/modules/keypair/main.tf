terraform {
  required_version = ">= 0.14.0"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53.0"
    }
  }
}

# Configure OpenStack provider with authentication and region
provider "openstack" {
  auth_url    = var.openstack_auth_url        # OpenStack Identity endpoint
  region      = var.openstack_region          # Region name
  user_name   = var.openstack_user_name       # Username for authentication
  tenant_name = var.openstack_tenant_name     # Project or tenant name
  password    = var.openstack_password        # Password

  # Optional override for compute endpoint
  endpoint_overrides = {
    compute = "http://10.102.192.230:8774/v2.1/"
  }
}

# Create an SSH keypair using local public key
resource "openstack_compute_keypair_v2" "my_key" {
  name       = "toanndcloud-keypair"                      # Key name in OpenStack
  public_key = file("${path.root}/tf-cloud-init.pub")     # Path to local public key file
}
