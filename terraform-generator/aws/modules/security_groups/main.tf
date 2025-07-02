data "aws_security_group" "default" {
  vpc_id = var.vpc_id
  name   = "default"
}
# modules/security_groups/main.tf
locals {
  # Định nghĩa tất cả rules trong module
  predefined_rules = {
    "web-sg" = {
      description = "Web traffic"
      ingress = [
        { from_port = 80, to_port = 80, protocol = "tcp", cidr_blocks = ["0.0.0.0/0"] },
        { from_port = 443, to_port = 443, protocol = "tcp", cidr_blocks = ["0.0.0.0/0"] }
      ]
    },
    "ssh-sg" = {
      description = "SSH access"
      ingress = [
        { from_port = 22, to_port = 22, protocol = "tcp", cidr_blocks = ["192.168.0.0/16"] }
      ]
    }
  }

  # Lọc chỉ các SG được yêu cầu
  groups_to_manage = {
    for name, rules in local.predefined_rules :
    name => rules if contains(var.required_security_groups, name) && name != "default"
  }
}

resource "aws_security_group" "this" {
  for_each = local.groups_to_manage

  name        = each.key
  description = each.value.description
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = each.value.ingress
    content {
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }

  dynamic "egress" {
    for_each = lookup(each.value, "egress", [{
      from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"]
    }])
    content {
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
    }
  }

}

output "group_ids" {
  value = merge(
    { "default" = data.aws_security_group.default.id }, # Thêm default SG vào output
    { for k, v in aws_security_group.this : k => v.id }
  )
}