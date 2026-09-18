resource "aws_elasticache_subnet_group" "main" {
  name = "${local.name_prefix}-valkey"

  subnet_ids = [
    for subnet
    in aws_subnet.private :
    subnet.id
  ]

  tags = {
    Name = (
      "${local.name_prefix}-valkey"
    )
  }
}


resource "random_password" "redis_auth" {
  count = (
    var.enable_managed_data_services
    ? 1
    : 0
  )

  length = 64

  special = false
}


resource "aws_ssm_parameter" "redis_auth" {
  count = (
    var.enable_managed_data_services
    ? 1
    : 0
  )

  name = (
    "/virelai/${var.environment}/redis/auth-token"
  )

  description = (
    "Authentication token for Virelai Valkey"
  )

  type = "SecureString"

  value = (
    random_password.redis_auth[0].result
  )

  tags = {
    Name = (
      "${local.name_prefix}-redis-auth"
    )
  }
}


resource "aws_elasticache_replication_group" "redis" {
  count = (
    var.enable_managed_data_services
    ? 1
    : 0
  )


  replication_group_id = (
    "${local.name_prefix}-redis"
  )

  description = (
    "Virelai realtime analytics cache"
  )


  engine = "valkey"

  engine_version = (
    var.valkey_engine_version
  )


  node_type = "cache.t4g.micro"

  port = 6379


  num_cache_clusters = 1


  automatic_failover_enabled = false

  multi_az_enabled = false


  subnet_group_name = (
    aws_elasticache_subnet_group.main.name
  )

  security_group_ids = [
    aws_security_group.redis.id,
  ]


  at_rest_encryption_enabled = true

  transit_encryption_enabled = true

  transit_encryption_mode = "required"


  auth_token = (
    random_password.redis_auth[0].result
  )


  snapshot_retention_limit = 0

  apply_immediately = true


  tags = {
    Name = (
      "${local.name_prefix}-redis"
    )
  }
}