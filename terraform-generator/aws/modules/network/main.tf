# Create VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr_block
  enable_dns_hostnames = true

  tags = {
    Name = "shared-vpc"
  }
}

# Create public subnets for bastion hosts
resource "aws_subnet" "public_subnet" {
  count = length(var.public_subnet_cidrs)

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index % length(var.availability_zones)]

  tags = {
    Name = "public-subnet-${count.index + 1}"
  }
}

# Create private subnets defined in variable
# Only create subnets that have gateway_ip (skip transit networks)
resource "aws_subnet" "private_subnet" {
  for_each = { for net in var.private_subnets : net.name => net if net.gateway_ip != null && net.gateway_ip != "" }

  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = var.availability_zones[0]

  tags = {
    Name = each.value.name
  }
}

# Create Internet Gateway for public subnets
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "custom-igw"
  }
}

# Route table for public subnets (internet access)
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "public-rt"
  }
}

# Associate public subnets with public route table
resource "aws_route_table_association" "public" {
  for_each = { for idx, subnet in aws_subnet.public_subnet : idx => subnet }

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# Create Elastic IP for NAT gateway if needed
resource "aws_eip" "nat" {
  count = length([for r in var.routers : r if r.external]) > 0 ? 1 : 0

  tags = {
    Name = "eip-nat"
  }
}

# Create NAT gateway if at least one router is external
resource "aws_nat_gateway" "nat" {
  count = length(aws_eip.nat)

  depends_on    = [aws_internet_gateway.igw]
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public_subnet[0].id

  tags = {
    Name = "custom-nat"
  }
}

# Create private route table (shared by all private subnets)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  # Add default route to NAT if any router is external
  dynamic "route" {
    for_each = length(aws_nat_gateway.nat) > 0 ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.nat[0].id
    }
  }

  tags = {
    Name = "private-rt"
  }
}

# Associate all private subnets with the shared private route table
resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private_subnet

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}
