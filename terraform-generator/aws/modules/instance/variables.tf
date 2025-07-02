variable "instance_name" {
  type = string
}

variable "ami_id" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "fixed_ip" {
  type = string
}
variable "user_data" {
  type = string
  default = null
}

variable "key_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "security_group_ids" {
  type = list(string) 
  
}