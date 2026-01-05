output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.shoeshine.api_endpoint
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.shoeshine.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.shoeshine.arn
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.shoeshine.repository_url
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.shoeshine.name
}

output "s3_bucket_name" {
  description = "S3 bucket name (if configured)"
  value       = var.s3_bucket != "" && !can(regex("^arn:aws:s3:::", var.s3_bucket)) ? var.s3_bucket : null
}
