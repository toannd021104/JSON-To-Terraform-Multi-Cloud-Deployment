output "private_ip" {
  value = openstack_compute_instance_v2.instance[var.instance_name].access_ip_v4
}