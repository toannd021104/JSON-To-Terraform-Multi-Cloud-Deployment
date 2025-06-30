terraform {
  required_version = ">= 0.14.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  topology = jsondecode(file("${path.module}/topology.json"))
}

# 🔑 SSH Key Pair
resource "aws_key_pair" "my_key" {
  key_name   = "toanndcloud-keypair"
  public_key = file("${path.root}/tf-cloud-init.pub")
}

# 🔐 Security Group for SSH
resource "aws_security_group" "ssh_access" {
  name        = "allow_ssh_access_for_bastion"
  description = "Allow SSH inbound traffic"
  vpc_id      = module.network.vpc_id

  ingress {
    description = "SSH from anywhere"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Cân nhắc giới hạn IP cho an toàn
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "allow_ssh_access"
  }
}

# 🛡 Bastion Host (Public Subnet)
resource "aws_instance" "bastion" {
  ami                         = "ami-03f8acd418785369b"
  instance_type               = "t2.micro"
  subnet_id                   = module.network.public_subnet_ids[0]
  key_name                    = aws_key_pair.my_key.key_name
  security_groups             = [aws_security_group.ssh_access.id]
  associate_public_ip_address = true
  user_data                   = file("${path.root}/tf-cloud-init")

  tags = {
    Name = "bastion-host"
  }
}

# 🌐 Network Module
module "network" {
  source              = "./modules/network"
  vpc_cidr_block      = var.vpc_cidr_block
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnets     = local.topology.networks
  availability_zones  = var.availability_zones
  routers             = local.topology.routers
}

# 🖥 Instance Module (Private Subnets)
module "instance" {
  depends_on = [module.network]
  source     = "./modules/instance"

  for_each = { for inst in local.topology.instances : inst.name => inst }

  vpc_id                        = module.network.vpc_id 
  security_group_ssh_ids        = [aws_security_group.ssh_access.id]
  instance_name                = each.value.name
  ami_id                       = lookup({
                                "vm1_acab79" = { ami = "ami-03f8acd418785369b", instance_type = "t2.micro" },
                                "s2_acab79"  = { ami = "ami-03f8acd418785369b", instance_type = "t3.medium" }
                              }, each.key, {}).ami
  instance_type                = lookup({
                                "vm1_acab79" = { ami = "ami-03f8acd418785369b", instance_type = "t2.micro" },
                                "s2_acab79"  = { ami = "ami-03f8acd418785369b", instance_type = "t3.medium" }
                              }, each.key, {}).instance_type
  subnet_id                    = module.network.private_subnet_ids[each.value.networks[0].name]
  fixed_ip                     = each.value.networks[0].ip
  user_data                    = each.value.cloud_init != null ? file("${path.module}/cloud_init/${each.value.cloud_init}") : null
  key_name                     = aws_key_pair.my_key.key_name
}
