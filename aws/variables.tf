variable "aws_region" {
  description = "Region của AWS"
  type        = string
  default     = "us-west-2"
}

variable "vpc_cidr_block" {
  description = "CIDR block của VPC"
  type        = string
  default     = "192.168.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Danh sách CIDR cho public subnets"
  type        = list(string)
  default     = ["192.168.0.0/24"]
}

variable "availability_zones" {
  description = "Danh sách Availability Zones"
  type        = list(string)
  default     = ["us-west-2a"]
}

variable "ami_id" {
  description = "ID của AMI cho EC2 instances"
  type        = string
  default     = "ami-03f8acd418785369b"  # AMI Ubuntu 20.04 cho us-west-2
}