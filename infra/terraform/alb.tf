resource "aws_lb" "api" {
  count = var.enable_public_alb ? 1 : 0

  name = "${local.name_prefix}-api"

  internal           = false
  load_balancer_type = "application"

  security_groups = [
    aws_security_group.alb.id,
  ]

  subnets = [
    for subnet
    in aws_subnet.public :
    subnet.id
  ]

  tags = {
    Name = "${local.name_prefix}-api"
  }
}


resource "aws_lb_target_group" "api" {
  count = var.enable_public_alb ? 1 : 0

  name = "${local.name_prefix}-api"

  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled = true

    path     = "/health"
    protocol = "HTTP"
    matcher  = "200"

    interval = 30
    timeout  = 5

    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Name = "${local.name_prefix}-api"
  }
}


resource "aws_lb_listener" "api_http" {
  count = var.enable_public_alb ? 1 : 0

  load_balancer_arn = aws_lb.api[0].arn

  port     = 80
  protocol = "HTTP"

  default_action {
    type = "forward"

    target_group_arn = (
      aws_lb_target_group.api[0].arn
    )
  }
}