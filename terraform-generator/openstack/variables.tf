

variable "openstack_auth_url" {
  description = "URL xác thực OpenStack"
  type        = string
  default     = "http://10.102.192.230:5000"
}

variable "openstack_region" {
  description = "Region của OpenStack"
  type        = string
  default     = "RegionOne" 
}

variable "openstack_tenant_name" {
  description = "Tên tenant/project trong OpenStack"
  type        = string
  default     = "dacn"
}

variable "openstack_user_name" {
  description = "Username trong OpenStack"
  type        = string
  default     = "dacn"
}

variable "openstack_password" {
  description = "Password của user trong OpenStack"
  type        = string
  default     = "47dd31ec570a445"
}

variable "external_network_id" {
  description = "ID của external network trong OpenStack"
  type        = string
  default     = "8990843f-fbc3-49f2-ad08-5eb9b263b23e"
}

variable "external_network_name" {
  description = "Tên của external network cho floating IP"
  type        = string
  default     = "public-network"
}
