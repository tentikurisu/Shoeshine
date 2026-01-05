provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type = string
  default = "us-east-1"
}

variable "environment" {
  description = "Environment (development, staging, production)"
  type = string
  default = "production"
}

variable "docker_image" {
  description = "ECR image URI for Shoeshine"
  type = string
}

variable "api_key" {
  description = "Shoesine API key for authentication"
  type = string
  default = ""
}

variable "lambda_memory" {
  description = "Lambda function memory (MB)"
  type = number
  default = 2048
}

variable "lambda_timeout" {
  description = "Lambda function timeout (seconds)"
  type = number
  default = 300
}
