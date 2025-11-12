terraform {
  required_version = ">= 0.14.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

# Configure the AWS provider using the region from variable
provider "aws" {
  region = var.aws_region
}

# ===============================================
# Load the topology from a JSON file
# Extract all required security group names
# ===============================================
locals {
  topology = jsondecode(file("${path.module}/topology.json"))

  # Automatically collect all unique security groups used by instances
required_security_groups = distinct(
    concat(
      flatten([
        for inst in local.topology.instances : lookup(inst, "security_groups", [])
      ]),
      ["ssh-sg"]
    )
  )
}

# ===============================================
# VPC and Subnet Setup
# - Creates VPC, public/private subnets, routers
# ===============================================
module "network" {
  source              = "./modules/network"
  vpc_cidr_block      = var.vpc_cidr_block
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnets     = local.topology.networks
  availability_zones  = var.availability_zones
  routers             = local.topology.routers
}

# ===============================================
# Security Groups Module
# - Creates all SGs used by instances
# ===============================================
module "security_group" {
  depends_on              = [module.network]
  source                  = "./modules/security_groups"
  vpc_id                  = "vpc-0f9e1d98274fae447"
  required_security_groups = local.required_security_groups
}

# ===============================================
# EC2 Instance Deployment Module
# - Loops through each instance defined in topology
# - Assigns SGs, AMIs, subnets, fixed IP, user-data, keypair, etc.
# ===============================================
module "instance" {
  depends_on = [module.network, module.security_group]
  source     = "./modules/instance"

  for_each   = { for inst in local.topology.instances : inst.name => inst }

  vpc_id     = "vpc-0f9e1d98274fae447"

  # Assign security groups for the instance (fallback to "default" if not found)
  security_group_ids = try(
    [for sg in each.value.security_groups : module.security_group.group_ids[sg]],
    [module.security_group.group_ids["default"]]
  )

  instance_name     = each.value.name

  # Lookup AMI and instance type based on instance name
  ami_id            = lookup({
    vm1 = { ami = "ami-03f8acd418785369b", instance_type = "t2.micro" },
    s2  = { ami = "ami-03f8acd418785369b", instance_type = "t2.micro" }
  }, each.key, {}).ami

  instance_type     = lookup({
    vm1 = { ami = "ami-03f8acd418785369b", instance_type = "t2.micro" },
    s2  = { ami = "ami-03f8acd418785369b", instance_type = "t2.micro" }
  }, each.key, {}).instance_type

  subnet_id         = module.network.private_subnet_ids[each.value.networks[0].name]
  fixed_ip          = each.value.networks[0].ip

  # Use a cloud-init script if specified
  user_data         = each.value.cloud_init != null ? file("${path.module}/cloud_init/${each.value.cloud_init}") : null

  key_name          = "toanndcloud-keypair"

  # Assign public IP only if floating_ip is set to "true"
  assign_public_ip  = try(each.value.floating_ip, false)
}

# ===============================================
# Bastion Host (Jumpbox)
# - Public instance used to SSH into private instances
# ===============================================
resource "aws_instance" "bastion" {
  ami                         = "ami-03f8acd418785369b"
  instance_type               = "t2.micro"
  subnet_id                   = module.network.public_subnet_ids[0]
  key_name                    = "toanndcloud-keypair"
  security_groups             = [module.security_group.group_ids["ssh-sg"]]
  associate_public_ip_address = true

  # Use cloud-init script for initial setup of bastion
  user_data = templatefile("${path.module}/cloud_init/bastion.sh", {
    file_content = file("${path.root}/modules/keypair/tf-cloud-init")
  })

  tags = {
    Name = "bastion-host"
  }
}
