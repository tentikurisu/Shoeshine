variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment (development, staging, production)"
  type        = string
  default     = "production"
}

variable "api_key" {
  description = "Shoeshine API key for authentication"
  type        = string
  default     = ""
  sensitive   = true
}

variable "lambda_memory" {
  description = "Lambda function memory (MB)"
  type        = number
  default     = 2048

  validation {
    condition     = can(regex("^(128|256|512|1024|1536|2048|3072|4096|5120|5632|6144|6656|7168|7680|8192|8704|9216|9728|10240)$", tostring(var.lambda_memory)))
    error_message = "lambda_memory must be a valid Lambda memory size (128-10240 in 64MB increments)."
  }
}

variable "lambda_timeout" {
  description = "Lambda function timeout (seconds)"
  type        = number
  default     = 300

  validation {
    condition     = var.lambda_timeout >= 1 && var.lambda_timeout <= 900
    error_message = "lambda_timeout must be between 1 and 900 seconds."
  }
}

variable "lambda_reserved_concurrency" {
  description = "Lambda reserved concurrency (0 = no limit)"
  type        = number
  default     = 0

  validation {
    condition     = var.lambda_reserved_concurrency >= 0
    error_message = "lambda_reserved_concurrency must be 0 or greater."
  }
}

variable "bedrock_model_id" {
  description = "Bedrock model ID (e.g., anthropic.claude-sonnet-4-20250507)"
  type        = string
  default     = ""
}

variable "s3_bucket" {
  description = "Optional S3 bucket for document storage (leave empty to skip). Use bucket name or ARN. NOTE: In aws-bedrock-only branch, bucket creation is disabled - use existing buckets."
  type        = string
  default     = ""
}

variable "allowed_s3_buckets" {
  description = "Comma-separated list of S3 buckets allowed for document retrieval. Leave empty to allow all buckets (not recommended)."
  type        = string
  default     = ""
}

variable "ecr_image_tag" {
  description = "ECR image tag to deploy"
  type        = string
  default     = "latest"
}
