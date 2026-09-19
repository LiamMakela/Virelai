resource "aws_cloudwatch_log_group" "kafka" {
  name = "/ecs/${local.name_prefix}/kafka"

  retention_in_days = 7

  tags = {
    Name = "${local.name_prefix}-kafka"
  }
}


resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "virelai.internal"

  description = "Private service discovery for Virelai"

  vpc = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-discovery"
  }
}


resource "aws_service_discovery_service" "kafka" {
  name = "kafka"

  dns_config {
    namespace_id = (
      aws_service_discovery_private_dns_namespace.main.id
    )

    routing_policy = "MULTIVALUE"

    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  tags = {
    Name = "${local.name_prefix}-kafka"
  }
}


resource "aws_ecs_task_definition" "kafka" {
  count = var.enable_kafka_service ? 1 : 0

  family = "${local.name_prefix}-kafka"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = 1024
  memory = 2048

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )


  container_definitions = jsonencode([
    {
      name = "kafka"

      image = "apache/kafka:4.2.1"

      essential = true


      portMappings = [
        {
          containerPort = 19092
          hostPort      = 19092
          protocol      = "tcp"
        }
      ]


      environment = [
        {
          name  = "KAFKA_NODE_ID"
          value = "1"
        },
        {
          name  = "KAFKA_PROCESS_ROLES"
          value = "broker,controller"
        },
        {
          name  = "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP"
          value = "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT"
        },
        {
          name  = "KAFKA_LISTENERS"
          value = "PLAINTEXT://:19092,CONTROLLER://:29093"
        },
        {
          name  = "KAFKA_ADVERTISED_LISTENERS"
          value = "PLAINTEXT://kafka.virelai.internal:19092"
        },
        {
          name  = "KAFKA_INTER_BROKER_LISTENER_NAME"
          value = "PLAINTEXT"
        },
        {
          name  = "KAFKA_CONTROLLER_LISTENER_NAMES"
          value = "CONTROLLER"
        },
        {
          name  = "KAFKA_CONTROLLER_QUORUM_VOTERS"
          value = "1@localhost:29093"
        },
        {
          name  = "CLUSTER_ID"
          value = "4L6g3nShT-eMCtK--X86sw"
        },
        {
          name  = "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR"
          value = "1"
        },
        {
          name  = "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR"
          value = "1"
        },
        {
          name  = "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR"
          value = "1"
        },
        {
          name  = "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS"
          value = "0"
        },
        {
          name  = "KAFKA_AUTO_CREATE_TOPICS_ENABLE"
          value = "true"
        },
        {
          name  = "KAFKA_LOG_DIRS"
          value = "/tmp/kraft-combined-logs"
        },
        {
          name  = "KAFKA_SHARE_COORDINATOR_STATE_TOPIC_REPLICATION_FACTOR"
          value = "1"
        },
        {
          name  = "KAFKA_SHARE_COORDINATOR_STATE_TOPIC_MIN_ISR"
          value = "1"
        }
      ]


      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group.kafka.name
          )

          awslogs-region = var.aws_region

          awslogs-stream-prefix = "kafka"
        }
      }
    }
  ])


  tags = {
    Name = "${local.name_prefix}-kafka"
  }
}


resource "aws_ecs_service" "kafka" {
  count = var.enable_kafka_service ? 1 : 0

  name = "${local.name_prefix}-kafka"

  cluster = aws_ecs_cluster.main.id

  task_definition = (
    aws_ecs_task_definition.kafka[0].arn
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


  service_registries {
    registry_arn = (
      aws_service_discovery_service.kafka.arn
    )
  }


  tags = {
    Name = "${local.name_prefix}-kafka"
  }
}