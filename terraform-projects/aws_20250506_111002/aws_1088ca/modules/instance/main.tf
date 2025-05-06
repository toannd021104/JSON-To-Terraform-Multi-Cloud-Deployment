resource "aws_instance" "main" {
  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id     = var.subnet_id
  private_ip    = var.fixed_ip
  
  tags = {
    Name = var.instance_name
  }
}