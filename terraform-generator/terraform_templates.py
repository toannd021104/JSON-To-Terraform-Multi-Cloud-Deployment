import textwrap
import json

# ===== AWS BLOCKS =====
def aws_terraform_block():
    return textwrap.dedent("""
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
    return textwrap.dedent("""
    # Configure the AWS provider using the region from variable
    provider "aws" {
      region = var.aws_region
    }
    """)

def aws_locals_block():
    return textwrap.dedent("""
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
    """)

def aws_network_module_block():
    return textwrap.dedent("""
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
    """)

def aws_security_group_block():
    return textwrap.dedent("""
    # ===============================================
    # Security Groups Module
    # - Creates all SGs used by instances
    # ===============================================
    module "security_group" {
      depends_on              = [module.network]
      source                  = "./modules/security_groups"
      vpc_id                  = module.network.vpc_id
      required_security_groups = local.required_security_groups
    }
    """)

def aws_instance_module_block(validated_map):
    return textwrap.dedent(f"""
    # ===============================================
    # EC2 Instance Deployment Module
    # - Loops through each instance defined in topology
    # - Assigns SGs, AMIs, subnets, fixed IP, user-data, keypair, etc.
    # ===============================================
    module "instance" {{
      depends_on = [module.network, module.security_group]
      source     = "./modules/instance"
      for_each   = {{ for inst in local.topology.instances : inst.name => inst }}
      vpc_id     = module.network.vpc_id
      # Assign security groups for the instance (fallback to "default" if not found)
      security_group_ids = try(
        [for sg in each.value.security_groups : module.security_group.group_ids[sg]],
        [module.security_group.group_ids["default"]]
      )
      instance_name     = each.value.name
      # Lookup AMI and instance type based on instance name
      ami_id            = lookup({json.dumps(validated_map)}, each.key, {{}}).ami
      instance_type     = lookup({json.dumps(validated_map)}, each.key, {{}}).instance_type
      subnet_id         = module.network.private_subnet_ids[each.value.networks[0].name]
      fixed_ip          = each.value.networks[0].ip
      # Use a cloud-init script if specified
      user_data         = each.value.cloud_init != null ? file("${{path.module}}/cloud_init/${{each.value.cloud_init}}") : null
      key_name          = "toanndcloud-keypair"
      # Assign public IP only if floating_ip is set to "true"
      assign_public_ip  = try(each.value.floating_ip, false)
    }}
    """)

def aws_bastion_block():
    return textwrap.dedent("""
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
    """)

def aws_keypair_block():
    return textwrap.dedent("""
    resource "aws_key_pair" "my_key" {
      key_name   = "toanndcloud-keypair"
      public_key = file("${path.root}/tf-cloud-init.pub")
    }
    """)

# ===== OPENSTACK BLOCKS =====
def os_terraform_block():
    return textwrap.dedent("""
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
    return textwrap.dedent("""
    # Configure the OpenStack provider using variables
    provider "openstack" {
      auth_url    = var.openstack_auth_url
      region      = var.openstack_region
      user_name   = var.openstack_user_name
      tenant_name = var.openstack_tenant_name
      password    = var.openstack_password
      # Override default compute endpoint if needed
      endpoint_overrides = {
        compute = "http://10.102.192.230:8774/v2.1/"
      }
    }
    """)

def os_locals_block():
    return textwrap.dedent("""
    # ========================================
    # Load topology data from a JSON file
    # ========================================
    locals {
      topology = jsondecode(file("${path.root}/topology.json"))
    }
    """)

def os_network_module_block():
    return textwrap.dedent("""
    # ========================================
    # Network Module
    # Creates networks and routers as defined in topology
    # ========================================
    module "network" {
      source              = "./modules/network"
      networks            = local.topology.networks
      routers             = local.topology.routers
      external_network_id = "c668f27f-c14b-410d-b1df-016adc280c6e"  # External (public) network ID
    }
    """)

def os_instance_module_block(validated_map):
    return textwrap.dedent(f"""
    # ========================================
    # Instance Module
    # Deploys VMs based on the topology file
    # ========================================
    module "instance" {{
      depends_on = [module.network]  # Ensure networking is provisioned first
      source     = "./modules/instance"
      # Loop through each instance defined in the topology file
      for_each = {{ for inst in local.topology.instances : inst.name => inst }}
      instance_name = each.value.name
      # Assign image and flavor for each instance
      image_name  = lookup({json.dumps(validated_map)}, each.key, {{}}).image
      flavor_name = lookup({json.dumps(validated_map)}, each.key, {{}}).flavor
      # Assign network and fixed IP to the instance
      network_id = module.network.network_ids[each.value.networks[0].name]
      fixed_ip   = each.value.networks[0].ip
      # Use cloud-init script if defined
      user_data = each.value.cloud_init != null ? file("${{path.root}}/cloud_init/${{each.value.cloud_init}}") : null
      # Configure SSH keypair and security groups (optional)
      key_pair        = lookup(each.value, "keypair", null)
      security_groups = lookup(each.value, "security_groups", ["default"])
      # Assign floating IP if provided
      floating_ip_address = lookup(each.value, "floating_ip", null)
    }}
    """)

