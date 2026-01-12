provider "aws" {
  region = var.aws_region
}

# ============================================================================
# ECR Repository
# ============================================================================

resource "aws_ecr_repository" "shoeshine" {
  name                 = "shoeshine"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = "Shoeshine"
    Environment = var.environment
  }
}

# Allow Lambda to pull images from ECR
resource "aws_ecr_repository_policy" "shoeshine" {
  repository = aws_ecr_repository.shoeshine.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaECRImageRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
      }
    ]
  })
}

# ============================================================================
# IAM Role for Lambda
# ============================================================================

resource "aws_iam_role" "lambda_exec" {
  name = "shoeshine-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project     = "Shoeshine"
    Environment = var.environment
  }
}

# Attach basic Lambda execution role
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom IAM policy for Lambda (Bedrock + S3)
data "aws_iam_policy_document" "lambda_policy" {
  dynamic "statement" {
    for_each = var.enable_bedrock ? [1] : []
    content {
      sid = "BedrockAccess"

      actions = [
        "bedrock:InvokeModel"
      ]

      resources = [
        "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      ]
    }
  }

  dynamic "statement" {
    for_each = var.allowed_s3_buckets != "" ? split(",", var.allowed_s3_buckets) : []
    content {
      sid = "S3Access-${statement.key}"

      actions = [
        "s3:GetObject",
        "s3:HeadObject"
      ]

      resources = [
        "${trimspace(statement.value)}/*"
      ]
    }
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name   = "shoeshine-lambda-${var.environment}"
  policy = data.aws_iam_policy_document.lambda_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_custom" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# ============================================================================
# CloudWatch Log Group
# ============================================================================

resource "aws_cloudwatch_log_group" "shoeshine" {
  name              = "/aws/lambda/shoeshine-${var.environment}"
  retention_in_days = 7

  tags = {
    Project     = "Shoeshine"
    Environment = var.environment
  }
}

# ============================================================================
# Lambda Function
# ============================================================================

resource "aws_lambda_function" "shoeshine" {
  function_name = "shoeshine-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn

  package_type = "Image"
  image_uri    = "${aws_ecr_repository.shoeshine.repository_url}:${var.ecr_image_tag}"

  memory_size = var.lambda_memory
  timeout     = var.lambda_timeout

  reserved_concurrent_executions = var.lambda_reserved_concurrency > 0 ? var.lambda_reserved_concurrency : null

  environment {
    variables = {
      SHOESHINE_ENV      = var.environment
      SHOESHINE_API_KEY  = var.api_key
      AWS_REGION         = var.aws_region
      BEDROCK_MODEL_ID   = var.enable_bedrock ? var.bedrock_model_id : ""
      ALLOWED_S3_BUCKETS = var.allowed_s3_buckets
    }
  }

  image_config {
    command = ["api_server.lambda_handler"]
  }

  depends_on = [
    aws_cloudwatch_log_group.shoeshine,
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_custom
  ]

  tags = {
    Project     = "Shoeshine"
    Environment = var.environment
  }
}

# ============================================================================
# API Gateway
# ============================================================================

resource "aws_apigatewayv2_api" "shoeshine" {
  name          = "shoeshine-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["*"]
    expose_headers    = ["*"]
    max_age           = 3600
  }

  tags = {
    Project     = "Shoeshine"
    Environment = var.environment
  }
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "shoeshine" {
  api_id      = aws_apigatewayv2_api.shoeshine.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Project     = "Shoeshine"
    Environment = var.environment
  }
}

# API Gateway Integration with Lambda
resource "aws_apigatewayv2_integration" "shoeshine" {
  api_id           = aws_apigatewayv2_api.shoeshine.id
  integration_type = "AWS_PROXY"

  integration_uri    = aws_lambda_function.shoeshine.arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

# Route all requests to Lambda
resource "aws_apigatewayv2_route" "shoeshine" {
  api_id    = aws_apigatewayv2_api.shoeshine.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.shoeshine.id}"
}

# Allow API Gateway to invoke Lambda
resource "aws_lambda_permission" "apigateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.shoeshine.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.shoeshine.execution_arn}/*/*"
}

# Optional: Create deployment for API Gateway (if needed for versioning)
resource "aws_apigatewayv2_deployment" "shoeshine" {
  api_id = aws_apigatewayv2_api.shoeshine.id

  triggers = {
    redeployment = timestamp()
  }

  depends_on = [
    aws_apigatewayv2_route.shoeshine
  ]

  lifecycle {
    create_before_destroy = true
  }
}
