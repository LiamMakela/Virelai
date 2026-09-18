resource "aws_db_subnet_group" "main" {
  name = "${local.name_prefix}-postgres"

  subnet_ids = [
    for subnet
    in aws_subnet.private :
    subnet.id
  ]

  tags = {
    Name = (
      "${local.name_prefix}-postgres"
    )
  }
}


resource "aws_db_instance" "postgres" {
  count = (
    var.enable_managed_data_services
    ? 1
    : 0
  )


  identifier = (
    "${local.name_prefix}-postgres"
  )


  engine = "postgres"

  engine_version = (
    var.postgres_engine_version
  )

  instance_class = (
    "db.t4g.micro"
  )


  db_name = "virelai"

  username = "virelai_admin"


  #
  # RDS generates the password and stores
  # it in AWS Secrets Manager.
  #
  # We do NOT put a DB password in Git,
  # terraform.tfvars, or Terraform output.
  #
  manage_master_user_password = true


  port = 5432


  allocated_storage = 20

  max_allocated_storage = 50

  storage_type = "gp3"

  storage_encrypted = true


  db_subnet_group_name = (
    aws_db_subnet_group.main.name
  )

  vpc_security_group_ids = [
    aws_security_group.rds.id,
  ]


  publicly_accessible = false

  multi_az = false


  backup_retention_period = 1

  copy_tags_to_snapshot = true


  auto_minor_version_upgrade = true

  apply_immediately = true


  performance_insights_enabled = false

  monitoring_interval = 0


  #
  # Dev environment:
  # easy to destroy without requiring
  # a final production snapshot.
  #
  deletion_protection = false

  skip_final_snapshot = true

  delete_automated_backups = true


  tags = {
    Name = (
      "${local.name_prefix}-postgres"
    )
  }
}