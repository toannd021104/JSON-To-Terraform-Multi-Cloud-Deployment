# Create an EC2 instance in a private subnet
resource "aws_instance" "main" {
  ami                    = var.ami_id                     # AMI to use
  instance_type          = var.instance_type              # EC2 instance type
  subnet_id              = var.subnet_id                  # Private subnet ID
  private_ip             = var.fixed_ip                   # Static private IP
  key_name               = var.key_name                   # SSH key pair name
  vpc_security_group_ids = var.security_group_ids         # Security groups
  user_data              = var.user_data                  # Optional cloud-init script

  tags = {
    Name = var.instance_name                              # Instance name tag
  }
}

# Allocate and associate an Elastic IP if needed
resource "aws_eip" "this" {
  count    = var.assign_public_ip ? 1 : 0                 # Only create if assign_public_ip is true
  instance = aws_instance.main.id                         # Attach EIP to instance

  tags = {
    Name = "${var.instance_name}-eip"                     # EIP name tag
  }

  depends_on = [aws_instance.main]                        # Ensure instance is created first
}
