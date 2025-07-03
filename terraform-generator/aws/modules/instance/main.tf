# 🖥 EC2 Instance in Private Subnet
resource "aws_instance" "main" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  private_ip                  = var.fixed_ip
  key_name                    = var.key_name
  vpc_security_group_ids      = var.security_group_ids
  user_data                   = var.user_data

  tags = {
    Name = var.instance_name
  }
}

resource "aws_eip" "this" {
  count    = var.assign_public_ip ? 1 : 0
  instance = aws_instance.main.id
  
  tags = {
    Name = "${var.instance_name}-eip"
  }

  depends_on = [aws_instance.main]
}

