locals {
  worker_names = toset([
    "transcoder",
    "analytics-worker",
    "realtime-worker",
  ])
}


resource "aws_cloudwatch_log_group" "worker" {
  for_each = (
    var.enable_worker_services
    ? local.worker_names
    : toset([])
  )

  name = "/ecs/${local.name_prefix}/${each.key}"

  retention_in_days = 7

  tags = {
    Name = "${local.name_prefix}-${each.key}"
  }
}


# ---------------------------------------------------------
# Transcoder
# ---------------------------------------------------------


resource "aws_ecs_task_definition" "transcoder" {
  count = var.enable_worker_services ? 1 : 0

  family = "${local.name_prefix}-transcoder"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = 1024
  memory = 2048

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )

  task_role_arn = (
    aws_iam_role.transcoder_task[0].arn
  )


  container_definitions = jsonencode([
    {
      name = "transcoder"

      image = (
        "${aws_ecr_repository.service["transcoder"].repository_url}:${var.worker_image_tag}"
      )

      essential = true


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
          name  = "KAFKA_BOOTSTRAP_SERVERS"
          value = "kafka.virelai.internal:19092"
        },
        {
          name  = "KAFKA_TOPIC_VIDEO_UPLOADED"
          value = "video.uploaded.v1"
        },

        {
          name  = "S3_ENDPOINT_URL"
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
        }
      ]


      secrets = [
        {
          name = "DB_PASSWORD"

          valueFrom = (
            "${aws_db_instance.postgres[0].master_user_secret[0].secret_arn}:password::"
          )
        }
      ]


      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group.worker["transcoder"].name
          )

          awslogs-region = var.aws_region

          awslogs-stream-prefix = "transcoder"
        }
      }
    }
  ])


  tags = {
    Name = "${local.name_prefix}-transcoder"
  }
}


resource "aws_ecs_service" "transcoder" {
  count = var.enable_worker_services ? 1 : 0

  name = "${local.name_prefix}-transcoder"

  cluster = aws_ecs_cluster.main.id

  task_definition = (
    aws_ecs_task_definition.transcoder[0].arn
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


  depends_on = [
    aws_ecs_service.kafka,
  ]


  tags = {
    Name = "${local.name_prefix}-transcoder"
  }
}


# ---------------------------------------------------------
# Analytics persistence worker
# ---------------------------------------------------------


resource "aws_ecs_task_definition" "analytics_worker" {
  count = var.enable_worker_services ? 1 : 0

  family = "${local.name_prefix}-analytics-worker"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = 256
  memory = 512

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )


  container_definitions = jsonencode([
    {
      name = "analytics-worker"

      image = (
        "${aws_ecr_repository.service["analytics-worker"].repository_url}:${var.worker_image_tag}"
      )

      essential = true


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
          name  = "KAFKA_BOOTSTRAP_SERVERS"
          value = "kafka.virelai.internal:19092"
        },
        {
          name  = "KAFKA_TOPIC_PLAYBACK_EVENTS"
          value = "playback.events.v1"
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
        }
      ]


      secrets = [
        {
          name = "DB_PASSWORD"

          valueFrom = (
            "${aws_db_instance.postgres[0].master_user_secret[0].secret_arn}:password::"
          )
        }
      ]


      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group.worker["analytics-worker"].name
          )

          awslogs-region = var.aws_region

          awslogs-stream-prefix = "analytics-worker"
        }
      }
    }
  ])


  tags = {
    Name = "${local.name_prefix}-analytics-worker"
  }
}


resource "aws_ecs_service" "analytics_worker" {
  count = var.enable_worker_services ? 1 : 0

  name = "${local.name_prefix}-analytics-worker"

  cluster = aws_ecs_cluster.main.id

  task_definition = (
    aws_ecs_task_definition.analytics_worker[0].arn
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


  depends_on = [
    aws_ecs_service.kafka,
  ]


  tags = {
    Name = "${local.name_prefix}-analytics-worker"
  }
}


# ---------------------------------------------------------
# Realtime worker
# ---------------------------------------------------------


resource "aws_ecs_task_definition" "realtime_worker" {
  count = var.enable_worker_services ? 1 : 0

  family = "${local.name_prefix}-realtime-worker"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = 256
  memory = 512

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )


  container_definitions = jsonencode([
    {
      name = "realtime-worker"

      image = (
        "${aws_ecr_repository.service["realtime-worker"].repository_url}:${var.worker_image_tag}"
      )

      essential = true


      environment = [
        {
          name  = "KAFKA_BOOTSTRAP_SERVERS"
          value = "kafka.virelai.internal:19092"
        },
        {
          name  = "KAFKA_TOPIC_PLAYBACK_EVENTS"
          value = "playback.events.v1"
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
          name  = "REDIS_USERNAME"
          value = "default"
        },
        {
          name  = "REDIS_TLS"
          value = "true"
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
        }
      ]


      secrets = [
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
            aws_cloudwatch_log_group.worker["realtime-worker"].name
          )

          awslogs-region = var.aws_region

          awslogs-stream-prefix = "realtime-worker"
        }
      }
    }
  ])


  tags = {
    Name = "${local.name_prefix}-realtime-worker"
  }
}


resource "aws_ecs_service" "realtime_worker" {
  count = var.enable_worker_services ? 1 : 0

  name = "${local.name_prefix}-realtime-worker"

  cluster = aws_ecs_cluster.main.id

  task_definition = (
    aws_ecs_task_definition.realtime_worker[0].arn
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


  depends_on = [
    aws_ecs_service.kafka,
  ]


  tags = {
    Name = "${local.name_prefix}-realtime-worker"
  }
}