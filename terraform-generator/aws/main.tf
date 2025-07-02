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
  # Tự động extract các SG cần thiết từ topology
  required_security_groups = distinct(flatten([
    for inst in local.topology.instances : lookup(inst, "security_groups", [])
  ]))
}

module "network" {
  source              = "./modules/network"
  vpc_cidr_block      = var.vpc_cidr_block
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnets     = local.topology.networks
  availability_zones  = var.availability_zones
  routers             = local.topology.routers
}

module "security_group" {
  depends_on = [module.network] 
  source                 = "./modules/security_groups"
  vpc_id                 = module.network.vpc_id
  required_security_groups = local.required_security_groups
}


module "instance" {
  depends_on = [module.network, module.security_group]
  source     = "./modules/instance"
  for_each = { for inst in local.topology.instances : inst.name => inst }
  vpc_id                       = module.network.vpc_id 
  security_group_ids = try(
    [for sg in each.value.security_groups : module.security_group.group_ids[sg]],
    [module.security_group.group_ids["default"]] # Sử dụng default SG từ output
  )
  instance_name                = each.value.name
  ami_id                       = lookup({"vm1": {"ami": "ami-03f8acd418785369b", "instance_type": "t3a.medium"}, "s2": {"ami": "ami-03f8acd418785369b", "instance_type": "t3a.medium"}}, each.key, {}).ami
  instance_type                = lookup({"vm1": {"ami": "ami-03f8acd418785369b", "instance_type": "t3a.medium"}, "s2": {"ami": "ami-03f8acd418785369b", "instance_type": "t3a.medium"}}, each.key, {}).instance_type
  subnet_id                    = module.network.private_subnet_ids[each.value.networks[0].name]
  fixed_ip                     = each.value.networks[0].ip
  user_data                    = each.value.cloud_init != null ? file("${path.module}/cloud_init/${each.value.cloud_init}") : null
  key_name                     = lookup(each.value, "keypair", null)
}
