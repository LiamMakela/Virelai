resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}


resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-igw"
  }
}


resource "aws_subnet" "public" {
  for_each = {
    for index, az
    in local.availability_zones :
    az => index
  }

  vpc_id = aws_vpc.main.id

  availability_zone = each.key

  cidr_block = cidrsubnet(
    var.vpc_cidr,
    8,
    each.value,
  )

  map_public_ip_on_launch = true

  tags = {
    Name = (
      "${local.name_prefix}-public-${each.key}"
    )

    Tier = "public"
  }
}


resource "aws_subnet" "private" {
  for_each = {
    for index, az
    in local.availability_zones :
    az => index
  }

  vpc_id = aws_vpc.main.id

  availability_zone = each.key

  cidr_block = cidrsubnet(
    var.vpc_cidr,
    8,
    each.value + 10,
  )

  map_public_ip_on_launch = false

  tags = {
    Name = (
      "${local.name_prefix}-private-${each.key}"
    )

    Tier = "private"
  }
}


resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"

    gateway_id = (
      aws_internet_gateway.main.id
    )
  }

  tags = {
    Name = "${local.name_prefix}-public-rt"
  }
}


resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id = each.value.id

  route_table_id = (
    aws_route_table.public.id
  )
}


resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-private-rt"
  }
}


resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id = each.value.id

  route_table_id = (
    aws_route_table.private.id
  )
}