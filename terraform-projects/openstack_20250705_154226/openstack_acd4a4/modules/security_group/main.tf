# Terraform settings and OpenStack provider
terraform {
  required_version = ">= 0.14.0"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53.0"
    }
  }
}

# OpenStack provider credentials
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

# SSH security group
resource "openstack_networking_secgroup_v2" "ssh_sg" {
  name        = "ssh-sg"
  description = "Allow SSH"
}

resource "openstack_networking_secgroup_rule_v2" "ssh_rule" {
  security_group_id = openstack_networking_secgroup_v2.ssh_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "192.168.0.0/16"  # Replace with trusted IP
}

# Web security group (HTTP + HTTPS)
resource "openstack_networking_secgroup_v2" "web_sg" {
  name        = "web-sg"
  description = "Allow web traffic"
}

resource "openstack_networking_secgroup_rule_v2" "http" {
  security_group_id = openstack_networking_secgroup_v2.web_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
}

resource "openstack_networking_secgroup_rule_v2" "https" {
  security_group_id = openstack_networking_secgroup_v2.web_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
}

# FTP security group
resource "openstack_networking_secgroup_v2" "ftp_sg" {
  name        = "ftp-sg"
  description = "Allow FTP"
}

# FTP control (port 21)
resource "openstack_networking_secgroup_rule_v2" "ftp_control" {
  security_group_id = openstack_networking_secgroup_v2.ftp_sg.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 21
  port_range_max    = 21
  remote_ip_prefix  = "0.0.0.0/0"
}

# FTP passive ports (49152–65534)
resource "openstack_networking_secgroup_rule_v2" "ftp_passive" {
  security_group_id = openstack_networking_secgroup_v2.ftp_sg.id
  direction         = "ingress"
  protocol          = "tcp"
  ethertype         = "IPv4"
  port_range_min    = 49152
  port_range_max    = 65534
  remote_ip_prefix  = "0.0.0.0/0"
}

# Database security group
resource "openstack_networking_secgroup_v2" "db_sg" {
  name        = "db-sg"
  description = "Allow DB access"
}

# MySQL (3306)
resource "openstack_networking_secgroup_rule_v2" "mysql" {
  security_group_id = openstack_networking_secgroup_v2.db_sg.id
  direction         = "ingress"
  protocol          = "tcp"
  ethertype         = "IPv4"
  port_range_min    = 3306
  port_range_max    = 3306
  remote_ip_prefix  = "192.168.0.0/16"
}

# PostgreSQL (5432)
resource "openstack_networking_secgroup_rule_v2" "postgresql" {
  security_group_id = openstack_networking_secgroup_v2.db_sg.id
  direction         = "ingress"
  protocol          = "tcp"
  port_range_min    = 5432
  port_range_max    = 5432
  ethertype         = "IPv4"
  remote_ip_prefix  = "192.168.0.0/16"
}
