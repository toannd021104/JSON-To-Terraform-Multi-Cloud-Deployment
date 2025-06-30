import textwrap
import json

# ===== AWS BLOCKS =====
def aws_terraform_block():
    return textwrap.dedent("""\
    terraform {
      required_version = ">= 0.14.0"
      required_providers {
        aws = {
          source  = "hashicorp/aws"
          version = "~> 4.0"
        }
      }
    }
    """)

def aws_provider_block():
    return textwrap.dedent("""\
    provider "aws" {
      region = var.aws_region
    }
    """)

def aws_locals_block():
    return textwrap.dedent("""\
    locals {
      topology = jsondecode(file("${path.module}/topology.json"))
    }
    """)

def aws_keypair_block():
    return textwrap.dedent("""\
    resource "aws_key_pair" "my_key" {
      key_name   = "toanndcloud-keypair"
      public_key = file("${path.root}/tf-cloud-init.pub")
    }
    """)

def aws_security_group_block():
    return textwrap.dedent("""\
    resource "aws_security_group" "ssh_access" {
      name        = "allow_ssh_access_for_bastion"
      description = "Allow SSH inbound traffic"
      vpc_id      = module.network.vpc_id

      ingress {
        description = "SSH from anywhere"
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
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
    """)

def aws_bastion_block():
    return textwrap.dedent("""\
    resource "aws_instance" "bastion" {
      ami                         = "ami-03f8acd418785369b"
      instance_type               = "t2.micro"
      subnet_id                   = module.network.public_subnet_ids[0]
      key_name                    = aws_key_pair.my_key.key_name
      vpc_security_group_ids      = [aws_security_group.ssh_access.id]
      associate_public_ip_address = true
      user_data                   = file("${path.root}/tf-cloud-init")

      tags = {
        Name = "bastion-host"
      }
    }
    """)

def aws_network_module_block():
    return textwrap.dedent("""\
    module "network" {
      source              = "./modules/network"
      vpc_cidr_block      = var.vpc_cidr_block
      public_subnet_cidrs = var.public_subnet_cidrs
      private_subnets     = local.topology.networks
      availability_zones  = var.availability_zones
      routers             = local.topology.routers
    }
    """)

def aws_instance_module_block(validated_map):
    return textwrap.dedent(f"""\
    module "instance" {{
      depends_on                = [module.network]
      source                    = "./modules/instance"
      for_each                  = {{ for inst in local.topology.instances : inst.name => inst }}
      vpc_id                    = module.network.vpc_id
      security_group_ssh_ids    = [aws_security_group.ssh_access.id]
      instance_name             = each.value.name
      ami_id                    = lookup({json.dumps(validated_map)}, each.key, {{}}).ami
      instance_type             = lookup({json.dumps(validated_map)}, each.key, {{}}).instance_type
      subnet_id                 = module.network.private_subnet_ids[each.value.networks[0].name]
      fixed_ip                  = each.value.networks[0].ip
      user_data                 = each.value.cloud_init != null ? file("${{path.module}}/cloud_init/${{each.value.cloud_init}}") : null
      key_name                  = aws_key_pair.my_key.key_name
    }}
    """)


# ===== OPENSTACK BLOCKS =====
def os_terraform_block():
    return textwrap.dedent("""\
    terraform {
      required_version = ">= 0.14.0"
      required_providers {
        openstack = {
          source  = "terraform-provider-openstack/openstack"
          version = "~> 1.53.0"
        }
      }
    }
    """)

def os_provider_block():
    return textwrap.dedent("""\
    provider "openstack" {
      auth_url    = var.openstack_auth_url
      region      = var.openstack_region
      user_name   = var.openstack_user_name
      tenant_name = var.openstack_tenant_name
      password    = var.openstack_password
      endpoint_overrides = {
        compute = "http://10.102.192.230:8774/v2.1/"
      }
    }
    """)

def os_locals_block():
    return textwrap.dedent("""\
    locals {
      topology = jsondecode(file("topology.json"))
    }
    """)

def os_keypair_block():
    return textwrap.dedent("""\
    resource "openstack_compute_keypair_v2" "my_key" {
      name       = "toanndcloud-keypair"
      public_key = file("${path.root}/tf-cloud-init.pub")
    }
    """)

def os_network_module_block():
    return textwrap.dedent("""\
    module "network" {
      source              = "./modules/network"
      networks            = local.topology.networks
      routers             = local.topology.routers
      external_network_id = var.external_network_id
    }
    """)

def os_instance_module_block(validated_map):
    return textwrap.dedent(f"""\
    module "instance" {{
      depends_on   = [module.network]
      source       = "./modules/instance"
      for_each     = {{ for inst in local.topology.instances : inst.name => inst }}
      instance_name = each.value.name
      image_name    = lookup({json.dumps(validated_map)}, each.key, {{}}).image
      flavor_name   = lookup({json.dumps(validated_map)}, each.key, {{}}).flavor
      network_id    = module.network.network_ids[each.value.networks[0].name]
      fixed_ip      = each.value.networks[0].ip
      user_data     = each.value.cloud_init != null ? file("${{path.module}}/cloud_init/${{each.value.cloud_init}}") : null
      key_pair      = openstack_compute_keypair_v2.my_key.name
      security_groups = ["default"] 
    }}
    """)
def os_bastion_block():
    return textwrap.dedent("""\
    resource "openstack_compute_instance_v2" "bastion" {
      name        = "bastion-host"
      image_name  = "ubuntu-jammy"
      flavor_name = "m2"
      key_pair    = openstack_compute_keypair_v2.my_key.name
      security_groups = ["default"]

      network {
        name = "public-network"
      }
    }
    """)