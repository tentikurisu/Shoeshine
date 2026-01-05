output "api_endpoint" {
  description = "Public API endpoint URL"
  value = aws_lb.shoeshine.dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value = aws_ecs_cluster.shoeshine.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value = aws_ecs_service.shoeshine_api.name
}

output "task_definition_arn" {
  description = "ECS task definition ARN"
  value = aws_ecs_task_definition.shoeshine.arn
}
