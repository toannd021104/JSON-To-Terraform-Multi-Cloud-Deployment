# Config tự động - Phiên bản 6f5bd7
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

        module "network" {
        source = "./modules/network"

        vpc_cidr_block     = var.vpc_cidr_block
        public_subnet_cidrs = var.public_subnet_cidrs
        private_subnets    = local.topology.networks
        availability_zones = var.availability_zones
        routers            = local.topology.routers
        }

        module "instance" {
            depends_on = [module.network]
            source = "./modules/instance"

            for_each = { for inst in local.topology.instances : inst.name => inst }

            instance_name = each.value.name
            ami_id        = lookup({"vm1_6f5bd7": {"ami": "ami-03f8acd418785369b", "instance_type": "t3.medium"}, "s2_6f5bd7": {"ami": "ami-03f8acd418785369b", "instance_type": "t3.medium"}}, each.key, {}).ami
            instance_type = lookup({"vm1_6f5bd7": {"ami": "ami-03f8acd418785369b", "instance_type": "t3.medium"}, "s2_6f5bd7": {"ami": "ami-03f8acd418785369b", "instance_type": "t3.medium"}}, each.key, {}).instance_type
            subnet_id     = module.network.private_subnet_ids[each.value.networks[0].name]
            fixed_ip      = each.value.networks[0].ip
            }

        output "instance_ips" {
        value = {
            for k, v in module.instance : k => v.private_ip
        }
        }
    