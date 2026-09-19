output "aws_region" {
  value = var.aws_region
}


output "vpc_id" {
  value = aws_vpc.main.id
}


output "public_subnet_ids" {
  value = [
    for subnet
    in aws_subnet.public :
    subnet.id
  ]
}


output "private_subnet_ids" {
  value = [
    for subnet
    in aws_subnet.private :
    subnet.id
  ]
}


output "originals_bucket" {
  value = aws_s3_bucket.originals.bucket
}


output "media_bucket" {
  value = aws_s3_bucket.media.bucket
}


output "ecr_repository_urls" {
  value = {
    for name, repository
    in aws_ecr_repository.service :
    name => repository.repository_url
  }
}


output "terraform_state_bucket" {
  value = aws_s3_bucket.terraform_state.bucket
}


output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}


output "database_address" {
  value = try(
    aws_db_instance.postgres[0].address,
    null,
  )
}


output "database_port" {
  value = try(
    aws_db_instance.postgres[0].port,
    null,
  )
}


output "database_name" {
  value = try(
    aws_db_instance.postgres[0].db_name,
    null,
  )
}


output "database_master_secret_arn" {
  value = try(
    aws_db_instance.postgres[0]
    .master_user_secret[0]
    .secret_arn,
    null,
  )
}


output "redis_primary_endpoint" {
  value = try(
    aws_elasticache_replication_group.redis[0]
    .primary_endpoint_address,
    null,
  )
}


output "redis_port" {
  value = try(
    aws_elasticache_replication_group.redis[0]
    .port,
    null,
  )
}


output "redis_auth_parameter_name" {
  value = try(
    aws_ssm_parameter.redis_auth[0].name,
    null,
  )
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}


output "api_load_balancer_dns" {
  value = try(
    aws_lb.api[0].dns_name,
    null,
  )
}


output "api_target_group_arn" {
  value = try(
    aws_lb_target_group.api[0].arn,
    null,
  )

}


output "ecs_execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}


output "api_task_role_arn" {
  value = aws_iam_role.api_task.arn
}

output "media_cloudfront_domain" {
  value = aws_cloudfront_distribution.media.domain_name
}