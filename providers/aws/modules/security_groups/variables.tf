variable "vpc_id" {
  description = "ID của VPC"
  type        = string
}

variable "required_security_groups" {
  description = "Danh sách tên các security groups cần đảm bảo tồn tại"
  type        = list(string)
  default     = ["default"] # Giá trị mặc định
}