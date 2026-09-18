resource "aws_ecr_repository" "service" {
  for_each = local.ecr_services

  name = (
    "${local.name_prefix}/${each.value}"
  )

  image_tag_mutability = "IMMUTABLE"


  image_scanning_configuration {
    scan_on_push = true
  }


  encryption_configuration {
    encryption_type = "AES256"
  }


  tags = {
    Name = (
      "${local.name_prefix}-${each.value}"
    )
  }
}


resource "aws_ecr_lifecycle_policy" "service" {
  for_each = aws_ecr_repository.service

  repository = each.value.name


  policy = jsonencode({
    rules = [
      {
        rulePriority = 1

        description = (
          "Keep the most recent 25 images"
        )

        selection = {
          tagStatus = "any"

          countType = (
            "imageCountMoreThan"
          )

          countNumber = 25
        }

        action = {
          type = "expire"
        }
      }
    ]
  })
}