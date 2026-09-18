locals {
  project = "virelai"

  name_prefix = (
    "${local.project}-${var.environment}"
  )

  availability_zones = slice(
    data.aws_availability_zones.available.names,
    0,
    2,
  )


  common_tags = {
    Project     = local.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }


  ecr_services = toset([
    "api",
    "ingest",
    "transcoder",
    "analytics-worker",
    "realtime-worker",
  ])
}