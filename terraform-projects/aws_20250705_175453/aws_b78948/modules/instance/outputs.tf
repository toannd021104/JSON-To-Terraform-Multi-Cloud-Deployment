output "private_ip" {
  value = aws_instance.main.private_ip
}

output "public_ip" {
  value = aws_instance.main.public_ip
}
