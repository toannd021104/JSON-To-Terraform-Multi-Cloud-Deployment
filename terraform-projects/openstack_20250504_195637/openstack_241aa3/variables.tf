variable "openstack_auth_url" {
  description = "URL xác thực OpenStack"
  type        = string
}

variable "openstack_region" {
  description = "Region của OpenStack"
  type        = string
}

variable "openstack_tenant_name" {
  description = "Tên tenant/project trong OpenStack"
  type        = string
}

variable "openstack_user_name" {
  description = "Username trong OpenStack"
  type        = string
}

variable "openstack_password" {
  description = "Password của user trong OpenStack"
  type        = string
  sensitive   = true
}

variable "external_network_id" {
  description = "ID của external network trong OpenStack"
  type        = string
}
