variable "instance_name" {
  type = string
}

variable "image_name" {
  type = string
}

variable "flavor_name" {
  type = string
}

variable "network_id" {
  type = string
}

variable "fixed_ip" {
  type = string
}
variable "user_data" {
  type = string
  default = null
}
variable "key_pair" {
  type = string
}
variable "security_groups" {
  type = list(string)
  default = []
}