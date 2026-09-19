variable "aws_region" {
  description = "AWS region used for Virelai."
  type        = string
  default     = "us-east-2"
}


variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition = contains(
      [
        "dev",
        "staging",
        "prod",
      ],
      var.environment,
    )

    error_message = (
      "environment must be dev, staging, or prod."
    )
  }
}


variable "vpc_cidr" {
  description = "CIDR range used by the Virelai VPC."
  type        = string
  default     = "10.30.0.0/16"
}


variable "frontend_origins" {
  description = "Origins allowed to directly upload to S3."
  type        = list(string)

  default = [
    "http://localhost:5173",
  ]
}


variable "enable_managed_data_services" {
  description = "Create billable RDS PostgreSQL and ElastiCache resources."
  type        = bool
  default     = false
}


variable "postgres_engine_version" {
  description = "RDS PostgreSQL engine version."
  type        = string
  default     = "17.11"
}


variable "valkey_engine_version" {
  description = "ElastiCache Valkey engine version."
  type        = string
  default     = "8.2"
}


variable "enable_api_service" {
  description = "Run the Virelai API on ECS Fargate."
  type        = bool
  default     = false
}


variable "api_image_tag" {
  description = "Immutable ECR image tag used by the API ECS task."
  type        = string
  default     = ""
}

variable "enable_kafka_service" {
  description = "Run the temporary Kafka broker on ECS Fargate."
  type        = bool
  default     = false
}

variable "enable_worker_services" {
  description = "Run the Virelai transcoder and analytics workers on ECS Fargate."
  type        = bool
  default     = false
}


variable "worker_image_tag" {
  description = "Immutable ECR image tag shared by the Virelai worker images."
  type        = string
  default     = ""
}

variable "enable_ingest_service" {
  description = "Run the telemetry ingest service on ECS Fargate."
  type        = bool
  default     = false
}

variable "ingest_image_tag" {
  description = "Immutable ECR image tag for the ingest service."
  type        = string
  default     = ""
}

variable "enable_public_alb" {
  description = "Create the public Application Load Balancer for API and ingest traffic."
  type        = bool
  default     = false
}