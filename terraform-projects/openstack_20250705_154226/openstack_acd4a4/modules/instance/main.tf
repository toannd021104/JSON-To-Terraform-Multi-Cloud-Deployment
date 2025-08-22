terraform {
  required_providers {
    openstack = {
      source = "terraform-provider-openstack/openstack"
    }
  }
}

# Create an OpenStack instance
resource "openstack_compute_instance_v2" "instance" {
  # Loop allows using the same pattern as other modules (even for single instance)
  for_each = { for inst in [var.instance_name] : inst => inst }

  name            = var.instance_name              # Instance name
  image_name      = var.image_name                 # Image to use
  flavor_name     = var.flavor_name                # Flavor 
  key_pair        = var.key_pair                   # SSH key pair
  security_groups = var.security_groups            # List of security groups

  network {
    uuid        = var.network_id                   # Network UUID
    fixed_ip_v4 = var.fixed_ip                     # Static internal IP
  }

  user_data = var.user_data                        # Optional cloud-init script
}

# Associate a floating IP with the instance if provided
resource "openstack_compute_floatingip_associate_v2" "fip_assoc" {
  # Only create if floating_ip_address is set
  for_each = { for inst in [var.instance_name] : inst => inst if var.floating_ip_address != null }

  floating_ip = var.floating_ip_address
  instance_id = openstack_compute_instance_v2.instance[each.key].id
}
