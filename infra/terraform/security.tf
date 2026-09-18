resource "aws_security_group" "ecs" {
  name = "${local.name_prefix}-ecs"

  description = (
    "Security group for future Virelai ECS tasks"
  )

  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-ecs"
  }
}


resource "aws_security_group" "rds" {
  name = "${local.name_prefix}-rds"

  description = (
    "Security group for Virelai PostgreSQL"
  )

  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rds"
  }
}


resource "aws_security_group" "redis" {
  name = "${local.name_prefix}-redis"

  description = (
    "Security group for Virelai Valkey"
  )

  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}


#
# Future ECS tasks may make outbound
# connections.
#
resource "aws_vpc_security_group_egress_rule" "ecs_all" {
  security_group_id = (
    aws_security_group.ecs.id
  )

  cidr_ipv4   = "0.0.0.0/0"
  ip_protocol = "-1"

  description = (
    "Allow outbound traffic from ECS"
  )
}


#
# Only ECS workloads may connect to
# PostgreSQL.
#
resource "aws_vpc_security_group_ingress_rule" "rds_from_ecs" {
  security_group_id = (
    aws_security_group.rds.id
  )

  referenced_security_group_id = (
    aws_security_group.ecs.id
  )

  from_port   = 5432
  to_port     = 5432
  ip_protocol = "tcp"

  description = (
    "PostgreSQL from Virelai ECS"
  )
}


#
# Only ECS workloads may connect to Valkey.
#
resource "aws_vpc_security_group_ingress_rule" "redis_from_ecs" {
  security_group_id = (
    aws_security_group.redis.id
  )

  referenced_security_group_id = (
    aws_security_group.ecs.id
  )

  from_port   = 6379
  to_port     = 6379
  ip_protocol = "tcp"

  description = (
    "Valkey from Virelai ECS"
  )
}