output "network_ids" {
  value = { for k, v in openstack_networking_network_v2.network : k => v.id }
}