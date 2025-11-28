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

variable "floating_ip_address" {
  description = "Floating IP: string IP to use, or null to skip"
  type        = string
  default     = null
}

variable "floating_ip_enabled" {
  description = "Whether to allocate a new floating IP (when floating_ip_address is null)"
  type        = bool
  default     = false
}

