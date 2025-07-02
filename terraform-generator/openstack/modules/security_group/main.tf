# ----------------------------
# Terraform Settings
# ----------------------------
terraform {
  required_version = ">= 0.14.0"  # Minimum Terraform version required

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"  # Source of the OpenStack provider
      version = "~> 1.53.0"  # Compatible OpenStack provider version
    }
  }
}

# ----------------------------
# OpenStack Provider Configuration
# ----------------------------
provider "openstack" {
  auth_url    = var.openstack_auth_url     # Identity endpoint (Keystone)
  region      = var.openstack_region       # OpenStack region to target
  user_name   = var.openstack_user_name    # Username for authentication
  tenant_name = var.openstack_tenant_name  # Project/Tenant name
  password    = var.openstack_password     # Password for authentication

  endpoint_overrides = {
    compute = "http://10.102.192.230:8774/v2.1/"  # Override for Nova compute service
  }
}

# ===================================================================================
# SSH Security Group: Allows SSH access from trusted IPs
# ===================================================================================
resource "openstack_networking_secgroup_v2" "ssh_sg" {
  name        = "ssh-sg"
  description = "Allow SSH access from trusted IPs"
}

resource "openstack_networking_secgroup_rule_v2" "ssh_rule" {
  security_group_id = openstack_networking_secgroup_v2.ssh_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "192.168.0.0/16"  # Replace with your local or trusted IP subnet
}

# ===================================================================================
# Web Security Group: Allows HTTP (80) and HTTPS (443) traffic from all sources
# ===================================================================================
resource "openstack_networking_secgroup_v2" "web_sg" {
  name        = "web-sg"
  description = "Allow HTTP/HTTPS traffic"
}

resource "openstack_networking_secgroup_rule_v2" "http" {
  security_group_id = openstack_networking_secgroup_v2.web_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"  # Allow from anywhere
}

resource "openstack_networking_secgroup_rule_v2" "https" {
  security_group_id = openstack_networking_secgroup_v2.web_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"  # Allow from anywhere
}

# ===================================================================================
# FTP Security Group: Allows FTP control and passive mode traffic
# ===================================================================================
resource "openstack_networking_secgroup_v2" "ftp_sg" {
  name        = "ftp-sg"
  description = "Allow FTP traffic"
}

# FTP Control Connection (Port 21)
resource "openstack_networking_secgroup_rule_v2" "ftp_control" {
  security_group_id = openstack_networking_secgroup_v2.ftp_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 21
  port_range_max    = 21
  remote_ip_prefix  = "0.0.0.0/0"  # Allow from anywhere
}

# FTP Passive Data Transfer Ports (49152–65534)
resource "openstack_networking_secgroup_rule_v2" "ftp_passive" {
  security_group_id = openstack_networking_secgroup_v2.ftp_sg.id
  direction         = "ingress"
  protocol          = "tcp"
  ethertype         = "IPv4"
  port_range_min    = 49152
  port_range_max    = 65534
  remote_ip_prefix  = "0.0.0.0/0"  # Allow from anywhere
}

# ===================================================================================
# Database Security Group: Allows internal access to MySQL and PostgreSQL
# ===================================================================================
resource "openstack_networking_secgroup_v2" "db_sg" {
  name        = "db-sg"
  description = "Allow database access"
}

# MySQL (Port 3306) - Internal access only
resource "openstack_networking_secgroup_rule_v2" "mysql" {
  security_group_id = openstack_networking_secgroup_v2.db_sg.id
  direction         = "ingress"
  protocol          = "tcp"
  ethertype         = "IPv4"
  port_range_min    = 3306
  port_range_max    = 3306
  remote_ip_prefix  = "192.168.0.0/16"  # Limit access to internal subnet
}

# PostgreSQL (Port 5432) - Internal access only
resource "openstack_networking_secgroup_rule_v2" "postgresql" {
  security_group_id = openstack_networking_secgroup_v2.db_sg.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 5432
  port_range_max    = 5432
  ethertype         = "IPv4"
  remote_ip_prefix  = "192.168.0.0/16"  # Limit access to internal subnet
}
