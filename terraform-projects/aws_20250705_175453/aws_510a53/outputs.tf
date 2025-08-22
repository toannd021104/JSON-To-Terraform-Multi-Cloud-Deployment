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

output "bastion_public_ip" {
  description = "Public IP của bastion host"
  value       = aws_instance.bastion.public_ip
}