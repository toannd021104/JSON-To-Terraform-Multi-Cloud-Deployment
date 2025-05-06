output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = { for k, v in aws_subnet.private_subnet : k => v.id }
}

output "public_subnet_ids" {
  value = [for subnet in aws_subnet.public_subnet : subnet.id]
}