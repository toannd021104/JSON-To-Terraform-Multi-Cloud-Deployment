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
      vpc_id                  = "vpc-0f9e1d98274fae447"
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
      vpc_id     = "vpc-0f9e1d98274fae447"
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
      user_data         = lookup(each.value, "cloud_init", null) != null ? file("${{path.module}}/cloud_init/${{lookup(each.value, "cloud_init", null)}}") : null
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

def aws_instance_only_outputs_block():
    """Outputs for instance-only folders (when using shared VPC)"""
    return textwrap.dedent("""
    # ===============================================
    # Outputs - Instance information only
    # ===============================================
    output "instance_private_ips" {
      description = "Map of instance names to private IPs"
      value = {
        for k, v in module.instance : k => v.private_ip
      }
    }

    output "instance_public_ips" {
      description = "Map of instance names to public IPs (if assigned)"
      value = {
        for k, v in module.instance : k => v.public_ip
      }
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

def os_keypair_module_block():
    return textwrap.dedent("""
    # ========================================
    # Keypair Module
    # Creates SSH keypair for instances
    # ========================================
    module "keypair" {
      source = "./modules/keypair"
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
      external_network_id = var.external_network_id
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
      user_data = lookup(each.value, "cloud_init", null) != null ? file("${{path.module}}/cloud_init/${{lookup(each.value, "cloud_init", null)}}") : null
      # Configure SSH keypair and security groups (optional)
      key_pair        = lookup(each.value, "keypair", null)
      security_groups = lookup(each.value, "security_groups", ["default"])
      # Floating IP configuration:
      # - floating_ip: true  → allocate new IP from external network
      # - floating_ip: "x.x.x.x" → use specific IP
      # - floating_ip: false/null → no floating IP
      floating_ip_enabled   = try(each.value.floating_ip == true, false)
      floating_ip_address   = try(tostring(each.value.floating_ip), null) != "true" && try(tostring(each.value.floating_ip), null) != "false" ? try(tostring(each.value.floating_ip), null) : null
    }}
    """)

# ===== AWS SHARED VPC BLOCKS =====
def aws_shared_vpc_terraform_block():
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

def aws_shared_vpc_provider_block():
    return textwrap.dedent("""
    # Configure the AWS provider using the region from variable
    provider "aws" {
      region = var.aws_region
    }
    """)

def aws_shared_vpc_locals_block(all_networks, all_routers):
    """Generate locals block with all networks from all copies"""
    return textwrap.dedent(f"""
    # ===============================================
    # Aggregated networks and routers from all copies
    # ===============================================
    locals {{
      # All networks from all topology copies
      all_networks = {json.dumps(all_networks, indent=4)}

      # All routers from all topology copies
      all_routers = {json.dumps(all_routers, indent=4)}

      # Automatically collect all unique security groups
      required_security_groups = distinct(
        concat(
          ["ssh-sg", "default"]
        )
      )
    }}
    """)

def aws_shared_vpc_network_module_block():
    """Create VPC and all subnets for all copies"""
    return textwrap.dedent("""
    # ===============================================
    # Shared VPC and Subnet Setup
    # - Creates ONE VPC for all copies
    # - Creates public/private subnets for all instances
    # ===============================================
    module "network" {
      source              = "./modules/network"
      vpc_cidr_block      = var.vpc_cidr_block
      public_subnet_cidrs = var.public_subnet_cidrs
      private_subnets     = local.all_networks
      availability_zones  = var.availability_zones
      routers             = local.all_routers
    }
    """)

def aws_shared_vpc_security_group_block():
    """Create security groups in the shared VPC"""
    return textwrap.dedent("""
    # ===============================================
    # Security Groups Module
    # - Creates all SGs in the shared VPC
    # ===============================================
    module "security_group" {
      depends_on              = [module.network]
      source                  = "./modules/security_groups"
      vpc_id                  = module.network.vpc_id
      required_security_groups = local.required_security_groups
    }
    """)

def aws_shared_vpc_bastion_block():
    """Create bastion host in the shared VPC"""
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
      vpc_security_group_ids      = [module.security_group.group_ids["ssh-sg"]]
      associate_public_ip_address = true

      tags = {
        Name = "bastion-host-shared"
      }
    }
    """)

def aws_shared_vpc_outputs_block():
    """Export VPC resources for instance copies to use"""
    return textwrap.dedent("""
    # ===============================================
    # Outputs - Exported for instance copies
    # ===============================================
    output "vpc_id" {
      value       = module.network.vpc_id
      description = "Shared VPC ID"
    }

    output "private_subnet_ids" {
      value       = module.network.private_subnet_ids
      description = "Map of subnet names to subnet IDs"
    }

    output "public_subnet_ids" {
      value       = module.network.public_subnet_ids
      description = "List of public subnet IDs"
    }

    output "security_group_ids" {
      value       = module.security_group.group_ids
      description = "Map of security group names to IDs"
    }

    output "bastion_public_ip" {
      value       = aws_instance.bastion.public_ip
      description = "Bastion host public IP"
    }
    """)

def aws_shared_vpc_variables_block(vpc_cidr="192.168.0.0/16", public_subnet_cidr="192.168.0.0/24"):
    """Variables for shared VPC"""
    return textwrap.dedent(f"""
    variable "aws_region" {{
      description = "AWS Region"
      type        = string
      default     = "us-west-2"
    }}

    variable "vpc_cidr_block" {{
      description = "CIDR block for VPC"
      type        = string
      default     = "{vpc_cidr}"
    }}

    variable "public_subnet_cidrs" {{
      description = "CIDR blocks for public subnets"
      type        = list(string)
      default     = ["{public_subnet_cidr}"]
    }}

    variable "availability_zones" {{
      description = "Availability Zones"
      type        = list(string)
      default     = ["us-west-2a"]
    }}
    """)

def aws_instance_with_remote_state_block(validated_map):
    """Instance module that uses remote state instead of creating VPC"""
    return textwrap.dedent(f"""
    # ===============================================
    # Load Shared VPC Resources from Remote State
    # ===============================================
    data "terraform_remote_state" "vpc" {{
      backend = "local"

      config = {{
        path = "${{path.module}}/../00-shared-vpc/terraform.tfstate"
      }}
    }}

    # ===============================================
    # EC2 Instance Deployment Module
    # - Uses shared VPC from remote state
    # - Loops through each instance defined in topology
    # ===============================================
    module "instance" {{
      depends_on = [data.terraform_remote_state.vpc]
      source     = "./modules/instance"
      for_each   = {{ for inst in local.topology.instances : inst.name => inst }}

      # Use VPC from remote state
      vpc_id = data.terraform_remote_state.vpc.outputs.vpc_id

      # Assign security groups from remote state
      security_group_ids = try(
        [for sg in each.value.security_groups : data.terraform_remote_state.vpc.outputs.security_group_ids[sg]],
        [data.terraform_remote_state.vpc.outputs.security_group_ids["default"]]
      )

      instance_name     = each.value.name
      # Lookup AMI and instance type based on instance name
      ami_id            = lookup(lookup({json.dumps(validated_map)}, each.key, {{}}), "ami", "ami-0030e4319cbf4dbf2")
      instance_type     = lookup(lookup({json.dumps(validated_map)}, each.key, {{}}), "instance_type", "t2.small")
      # Use subnet from remote state
      subnet_id         = data.terraform_remote_state.vpc.outputs.private_subnet_ids[each.value.networks[0].name]
      fixed_ip          = each.value.networks[0].ip
      # Use cloud-init script if specified
      user_data         = each.value.cloud_init != null ? file("${{path.module}}/cloud_init/${{each.value.cloud_init}}") : null
      key_name          = "toanndcloud-keypair"
      # Assign public IP only if floating_ip is set to "true"
      assign_public_ip  = try(each.value.floating_ip, false)
    }}
    """)

