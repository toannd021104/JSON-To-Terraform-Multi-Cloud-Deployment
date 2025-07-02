output "instance_private_ips" {
  description = "Map của instance names và private IPs"
  value = {
    for k, v in module.instance : k => v.private_ip
  }
}

output "private_subnet_ids" {
  description = "Map của private subnet IDs"
  value = module.network.private_subnet_ids
}

output "puclic_ip"{
  value = {
    for k, v in module.instance : k => v.public_ip
  }
}
