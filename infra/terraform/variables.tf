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