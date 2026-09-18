data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type = "Service"

      identifiers = [
        "ecs-tasks.amazonaws.com",
      ]
    }

    actions = [
      "sts:AssumeRole",
    ]
  }
}


resource "aws_iam_role" "ecs_execution" {
  name = "${local.name_prefix}-ecs-execution"

  assume_role_policy = (
    data.aws_iam_policy_document
    .ecs_task_assume_role
    .json
  )

  tags = {
    Name = "${local.name_prefix}-ecs-execution"
  }
}


resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role = aws_iam_role.ecs_execution.name

  policy_arn = (
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  )
}


resource "aws_iam_role" "api_task" {
  name = "${local.name_prefix}-api-task"

  assume_role_policy = (
    data.aws_iam_policy_document
    .ecs_task_assume_role
    .json
  )

  tags = {
    Name = "${local.name_prefix}-api-task"
  }
}


data "aws_iam_policy_document" "api_task" {
  statement {
    sid = "OriginalsBucket"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:AbortMultipartUpload",
      "s3:ListBucketMultipartUploads",
      "s3:ListMultipartUploadParts",
    ]

    resources = [
      aws_s3_bucket.originals.arn,
      "${aws_s3_bucket.originals.arn}/*",
    ]
  }


  statement {
    sid = "MediaBucket"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.media.arn}/*",
    ]
  }
}


resource "aws_iam_role_policy" "api_task" {
  name = "${local.name_prefix}-api"

  role = aws_iam_role.api_task.id

  policy = (
    data.aws_iam_policy_document
    .api_task
    .json
  )
}

data "aws_iam_policy_document" "ecs_execution_secrets" {
  count = (
    var.enable_managed_data_services
    ? 1
    : 0
  )

  statement {
    actions = [
      "secretsmanager:GetSecretValue",
    ]

    resources = [
      aws_db_instance.postgres[0]
        .master_user_secret[0]
        .secret_arn,
    ]
  }
}


resource "aws_iam_role_policy" "ecs_execution_secrets" {
  count = (
    var.enable_managed_data_services
    ? 1
    : 0
  )

  name = "${local.name_prefix}-ecs-secrets"

  role = aws_iam_role.ecs_execution.id

  policy = (
    data.aws_iam_policy_document
      .ecs_execution_secrets[0]
      .json
  )
}