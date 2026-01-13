# Look up the default security group in the VPC
data "aws_security_group" "default" {
  vpc_id = var.vpc_id
  name   = "default"
}

# Define security group rules and filter based on required inputs
locals {
  # All predefined security groups and their rules
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
        { from_port = 22, to_port = 22, protocol = "tcp", cidr_blocks = ["0.0.0.0/0"] }
      ],
      egress = [
        { from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"] }
      ]
    },
    "allow-all-sg" = {
      description = "Allow all traffic"
      ingress = [
        { from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"] }
      ]
      egress = [
        { from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"] }
      ]
    }
  }

  # Only manage the requested security groups (excluding "default")
  groups_to_manage = {
    for name, rules in local.predefined_rules :
    name => rules if contains(var.required_security_groups, name) && name != "default"
  }
}

# Create requested security groups and apply ingress/egress rules
resource "aws_security_group" "this" {
  for_each = local.groups_to_manage

  name        = each.key
  description = each.value.description
  vpc_id      = var.vpc_id

  # Ingress rules
  dynamic "ingress" {
    for_each = each.value.ingress
    content {
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }

  # Egress rules (default to allow all if not specified)
  dynamic "egress" {
    for_each = lookup(each.value, "egress", [
      { from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"] }
    ])
    content {
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
    }
  }
}

# Add ingress rule to AWS default security group to allow all traffic
resource "aws_security_group_rule" "default_allow_all_ingress" {
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = data.aws_security_group.default.id
  description       = "Allow all inbound traffic"
}

# Output map of all security group IDs
output "group_ids" {
  value = merge(
    { "default" = data.aws_security_group.default.id },
    { for k, v in aws_security_group.this : k => v.id }
  )
}
