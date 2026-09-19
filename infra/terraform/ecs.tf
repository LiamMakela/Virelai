resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    Name = "${local.name_prefix}-cluster"
  }
}


resource "aws_cloudwatch_log_group" "api" {
  name = "/ecs/${local.name_prefix}/api"

  retention_in_days = 7

  tags = {
    Name = "${local.name_prefix}-api"
  }
}
resource "aws_ecs_task_definition" "api" {
  count = var.enable_api_service ? 1 : 0

  family = "${local.name_prefix}-api"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = 256
  memory = 512

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )

  task_role_arn = (
    aws_iam_role.api_task.arn
  )


  container_definitions = jsonencode([
    {
      name = "api"

      image = (
        "${aws_ecr_repository.service["api"].repository_url}:${var.api_image_tag}"
      )

      essential = true


      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]


      environment = [
        {
          name  = "DB_HOST"
          value = aws_db_instance.postgres[0].address
        },
        {
          name  = "DB_PORT"
          value = tostring(aws_db_instance.postgres[0].port)
        },
        {
          name  = "DB_NAME"
          value = aws_db_instance.postgres[0].db_name
        },
        {
          name  = "DB_USER"
          value = aws_db_instance.postgres[0].username
        },

        {
          name  = "S3_ENDPOINT_URL"
          value = "https://s3.${var.aws_region}.amazonaws.com"
        },
        {
          name  = "S3_PUBLIC_ENDPOINT_URL"
          value = "https://s3.${var.aws_region}.amazonaws.com"
        },
        {
          name  = "S3_USE_DEFAULT_CREDENTIALS"
          value = "true"
        },
        {
          name  = "S3_REGION"
          value = var.aws_region
        },
        {
          name  = "S3_BUCKET_ORIGINALS"
          value = aws_s3_bucket.originals.bucket
        },
        {
          name  = "S3_BUCKET_MEDIA"
          value = aws_s3_bucket.media.bucket
        },

        {
          name  = "OTEL_TRACES_EXPORTER"
          value = "none"
        },
        {
          name  = "OTEL_METRICS_EXPORTER"
          value = "none"
        },
        {
          name  = "OTEL_LOGS_EXPORTER"
          value = "none"
        },
        {
          name  = "KAFKA_BOOTSTRAP_SERVERS"
          value = "kafka.virelai.internal:19092"
        },
        {
          name  = "REDIS_HOST"
          value = aws_elasticache_replication_group.redis[0].primary_endpoint_address
        },
        {
          name  = "REDIS_PORT"
          value = tostring(aws_elasticache_replication_group.redis[0].port)
        },
        {
          name  = "REDIS_TLS"
          value = "true"
        },
        {
          name = "MEDIA_PUBLIC_BASE_URL"

          value = (
            "https://${aws_cloudfront_distribution.media.domain_name}"
          )
        }
      ]


      secrets = [
        {
          name = "DB_PASSWORD"

          valueFrom = (
            "${aws_db_instance.postgres[0].master_user_secret[0].secret_arn}:password::"
          )
        },
        {
          name = "REDIS_PASSWORD"

          valueFrom = (
            aws_ssm_parameter.redis_auth[0].arn
          )
        }
      ]


      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group.api.name
          )

          awslogs-region = var.aws_region

          awslogs-stream-prefix = "api"
        }
      }
    }
  ])


  tags = {
    Name = "${local.name_prefix}-api"
  }
}


resource "aws_ecs_service" "api" {
  count = var.enable_api_service ? 1 : 0

  name = "${local.name_prefix}-api"

  cluster = aws_ecs_cluster.main.id

  task_definition = (
    aws_ecs_task_definition.api[0].arn
  )

  desired_count = 1

  launch_type = "FARGATE"


  network_configuration {
    subnets = [
      for subnet
      in aws_subnet.public :
      subnet.id
    ]

    security_groups = [
      aws_security_group.ecs.id,
    ]

    assign_public_ip = true
  }


  load_balancer {
    target_group_arn = (
      aws_lb_target_group.api.arn
    )

    container_name = "api"
    container_port = 8000
  }


  health_check_grace_period_seconds = 60


  depends_on = [
    aws_lb_listener.api_http,
  ]


  tags = {
    Name = "${local.name_prefix}-api"
  }
}