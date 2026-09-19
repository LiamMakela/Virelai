resource "aws_cloudwatch_log_group" "ingest" {
  name = "/ecs/${local.name_prefix}/ingest"

  retention_in_days = 7

  tags = {
    Name = "${local.name_prefix}-ingest"
  }
}



resource "aws_lb_target_group" "ingest" {
  count = (
    var.enable_public_alb
    && var.enable_ingest_service
    ? 1
    : 0
  )

  name = "${local.name_prefix}-ingest"

  port        = 8001
  protocol    = "HTTP"
  target_type = "ip"

  vpc_id = aws_vpc.main.id

  health_check {
    enabled = true

    path = "/health"

    protocol = "HTTP"

    matcher = "200"
  }

  tags = {
    Name = "${local.name_prefix}-ingest"
  }
}


resource "aws_lb_listener_rule" "ingest" {
  count = (
    var.enable_public_alb
    && var.enable_ingest_service
    ? 1
    : 0
  )

  listener_arn = aws_lb_listener.api_http[0].arn

  priority = 100

  action {
    type = "forward"

    target_group_arn = (
      aws_lb_target_group.ingest[0].arn
    )
  }

  condition {
    path_pattern {
      values = [
        "/events/*",
      ]
    }
  }
}


resource "aws_vpc_security_group_ingress_rule" "ecs_ingest_from_alb" {
  security_group_id = aws_security_group.ecs.id

  referenced_security_group_id = (
    aws_security_group.alb.id
  )

  from_port = 8001
  to_port   = 8001

  ip_protocol = "tcp"

  description = "Telemetry ingest traffic from ALB"
}


resource "aws_ecs_task_definition" "ingest" {
  count = var.enable_ingest_service ? 1 : 0

  family = "${local.name_prefix}-ingest"

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
      name = "ingest"

      image = (
        "${aws_ecr_repository.service["ingest"].repository_url}:${var.ingest_image_tag}"
      )

      essential = true

      portMappings = [
        {
          containerPort = 8001
          hostPort      = 8001
          protocol      = "tcp"
        }
      ]


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


      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group.ingest.name
          )

          awslogs-region = var.aws_region

          awslogs-stream-prefix = "ingest"
        }
      }
    }
  ])


  tags = {
    Name = "${local.name_prefix}-ingest"
  }
}


resource "aws_ecs_service" "ingest" {
  count = var.enable_ingest_service ? 1 : 0

  name = "${local.name_prefix}-ingest"

  cluster = aws_ecs_cluster.main.id

  task_definition = (
    aws_ecs_task_definition.ingest[0].arn
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
      aws_lb_target_group.ingest[0].arn
    )

    container_name = "ingest"
    container_port = 8001
  }


  depends_on = [
    aws_lb_listener.api_http,
    aws_lb_listener_rule.ingest,
    aws_ecs_service.kafka,
  ]


  tags = {
    Name = "${local.name_prefix}-ingest"
  }
}