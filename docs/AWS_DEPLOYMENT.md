# AWS Deployment Guide for Shoeshine

This guide explains how to deploy Shoeshine on AWS using various methods.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Option 1: EC2 (Simplest)](#option-1-ec2-simplest)
- [Option 2: ECS Fargate](#option-2-ecs-fargate)
- [Option 3: Lambda (Serverless)](#option-3-lambda-serverless)
- [Terraform Templates](#terraform-templates)
- [Manual Deployment Steps](#manual-deployment-steps)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools
- AWS CLI installed and configured
- Docker installed locally
- Git installed
- Basic understanding of AWS services

### Required AWS Services
- Amazon ECR (Elastic Container Registry)
- Amazon ECS (Elastic Container Service) OR AWS Lambda
- Application Load Balancer (optional, for ECS)
- Amazon Bedrock (if using /harvest endpoint)

### IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ShoesineECR",
      "Effect": "Allow",
      "Principal": {
        "AWS": "ec2.amazonaws.com",
        "AWS": "ecs-tasks.amazonaws.com",
        "AWS": "lambda.amazonaws.com"
      },
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer"
      ]
    },
    {
      "Sid": "ShoesineLambda",
      "Effect": "Allow",
      "Principal": {
        "AWS": "lambda.amazonaws.com"
      },
      "Action": [
        "lambda:InvokeFunction"
      ]
    },
    {
      "Sid": "ShoesineBedrock",
      "Effect": "Allow",
      "Principal": {
        "AWS": "bedrock.amazonaws.com"
      },
      "Action": [
        "bedrock:InvokeModel"
      ]
    }
  ]
}
```

---

## Option 1: EC2 (Simplest)

**Best for:** Development, small production, quick setup
**Cost:** ~$25-30/month

### Steps

1. **Launch EC2 Instance**
   ```bash
   # Using AWS CLI
   aws ec2 run-instances \
     --image-id ami-0c55b159cbf5618f64b2e20519c6f093b15 \  # Ubuntu 24.04 LTS (US East) \
     --instance-type t3.medium \
     --key-name shoeshine-api \
     --security-group-ids sg-xxxxxxxx \
     --iam-instance-profile shoeshine-ec2-role \
     --user-data "#!/bin/bash
     apt-get update
     apt-get install -y docker.io
     usermod -aG docker ubuntu
     docker run -d -p 8000:8000 --restart unless-stopped ghcr.io/yourusername/shoeshine-api:latest"
   "
   ```

2. **Security Group Configuration**
   ```bash
   aws ec2 authorize-security-group-ingress \
     --group-id sg-xxxxxxxx \
     --protocol tcp \
     --port 8000 \
     --cidr 0.0.0.0/0
   ```

3. **Connect and Verify**
   ```bash
   # Connect to instance
   ssh -i ubuntu@<public-ip>

   # Check Docker is running
   docker ps

   # Test API
   curl http://localhost:8000/health
   ```

4. **Optional: Configure Nginx Reverse Proxy**
   ```nginx
   server {
       listen 80;
       server_name api.yourdomain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $http_host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

---

## Option 2: ECS Fargate

**Best for:** Production, auto-scaling, pay-per-use
**Cost:** ~$15-25/month (depends on traffic)

### Steps

1. **Create ECR Repository**
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | \
     docker login -u AWS --password-stdin \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com

   # Create repository
   aws ecr create-repository \
     --repository-name shoeshine-api \
     --region us-east-1
   ```

2. **Build and Push Docker Image**
   ```bash
   # Build multi-arch image
   docker buildx build --platform linux/amd64 -t shoeshine-amd64 .
   docker buildx build --platform linux/arm64 -t shoeshine-arm64 .

   # Tag and push
   docker tag shoeshine-amd64 <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:latest
   docker tag shoeshine-amd64 <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:amd64:latest
   docker tag shoeshine-amd64 <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:latest

   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:amd64:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:arm64:latest
   ```

3. **Create ECS Task Definition**
   ```json
   {
     "family": "shoeshine",
     "networkMode": "awsvpc",
     "requiresCompatibilities": [
       {
         "cpu": "2048",
         "memory": "4096",
         "requiresCompatibilities": [
           {
             "cpu": "2048",
             "memory": "4096"
           }
         ]
       }
     ],
     "containerDefinitions": [
       {
         "name": "shoeshine",
         "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:latest",
         "memory": 4096,
         "cpu": 2048,
         "essential": true,
         "portMappings": [
           {
             "containerPort": 8000,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {
             "name": "SHOESHINE_OCR_ENGINE",
             "value": "easyocr"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/aws/shoeshine",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "shoeshine"
           }
         }
       }
     ],
     "taskRoleArn": "arn:aws:iam::123456789012:role/shoeshine-ecs-task-role"
   }
   ```

4. **Create ECS Service**
   ```bash
   aws ecs create-service \
     --cluster shoeshine-cluster \
     --service-name shoeshine-api \
     --task-definition shoeshine \
     --desired-count 2 \
     --launch-type FARGATE \
     --platform-version LATEST \
     --health-check-grace-period-seconds=30 \
     --health-check-interval-seconds=60
     --health-check-path /health \
     --health-check-protocol HTTP

   # Create target group for load balancer
   aws elbv2 create-target-group \
     --name shoeshine-api \
     --port 8000 \
     --protocol TCP \
     --target-type ip \
     --vpc-id <your-vpc-id>

   # Create load balancer
   aws elbv2 create-load-balancer \
     --name shoeshine-api-lb \
     --type network \
     --scheme internet-facing \
     --subnets <subnet-1> <subnet-2>

   # Register targets
   aws elbv2 register-targets \
     --target-group-arn arn:aws:elasticloadbalancing:target-group/shoeshine-api/123456789012 \
     --targets <ecs-task-id-1> <ecs-task-id-2> \
     --port 8000
   ```

5. **Auto-Scaling Configuration**
   ```bash
   aws application-autoscaling register-scalable-target \
     --service-namespace ecs \
     --scalable-dimension ecs:service:shoeshine-cluster:shoeshine-api \
     --target-id arn:aws:elasticloadbalancing:target-group/shoeshine-api/123456789012 \
     --min-capacity 1 \
     --max-capacity 10 \
     --resource-cpu-target-value 512
     --resource-cpu-scale-out-cooldown 300 \
     --resource-cpu-scale-in-cooldown 300
   ```

---

## Option 3: Lambda (Serverless)

**Best for:** Low traffic, pay-per-request
**Cost:** ~$5-15/month (depending on usage)

### Steps

1. **Create Lambda Layer for EasyOCR Models** (Optional)
   ```bash
   # Create a custom layer with EasyOCR models (~300MB)
   # This reduces cold start time

   aws lambda publish-layer-version \
     --layer-name shoeshine-easyocr-models \
     --zip-file easyocr-models.zip \
     --compatible-runtimes python3.11 \
     --description "EasyOCR pretrained models"
   ```

2. **Deploy Lambda Function**
   ```bash
   # Create function
   aws lambda create-function \
     --function-name shoeshine-api \
     --runtime python3.11 \
     --handler api_server.lambda_handler \
     --role arn:aws:iam::123456789012:role/shoeshine-lambda-role \
     --memory-size 2048 \
     --timeout 300 \
     --environment Variables="{SHOESHINE_ENV=production}" \
     --timeout 120 \
     --image <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine:latest

   # Configure function URL
   aws lambda create-function-url-config \
     --function-name shoeshine-api \
     --auth-type NONE \
     --unreserved-mode
   ```

3. **Set Up API Gateway**
   ```bash
   # Create REST API
   aws apigateway create-rest-api \
     --name shoeshine-api \
     --description "Document scanning API" \
     --region us-east-1 \
     --endpoint-types REGIONAL

   # Create resource
   aws apigateway create-resource \
     --rest-api-id <rest-api-id> \
     --parent-id / \
     --path-part "{proxy+}" \
     --path-part documents \
     --path-part extract

   # Create method
   aws apigateway put-method \
     --rest-api-id <rest-api-id> \
     --resource-id <resource-id> \
     --http-method POST

   # Create integration
   aws apigateway put-integration \
     --rest-api-id <rest-api-id> \
     --resource-id <resource-id> \
     --http-method POST \
     --type LAMBDA \
     --integration-uri arn:aws:lambda:us-east-1:123456789012:function:shoeshine-api \
     --timeout-ms 29000

   # Deploy
   aws apigateway create-deployment \
     --rest-api-id <rest-api-id> \
     --stage-name prod \
     --deployment-canary-settings-percentages 10

   # Grant permission
   aws lambda add-permission \
     --function-name shoeshine-api \
     --statement-id apigateway-invoke \
     --action lambda:InvokeFunction \
     --principal apigateway.amazonaws.com \
     --source-arn arn:aws:execute-api:us-east-1:<rest-api-id>

   # Wait for deployment (1-2 minutes)
   aws apigateway get-deployments \
     --rest-api-id <rest-api-id> \
     --stage-name prod
   ```

4. **Configure Bedrock Access**
   ```bash
   # Ensure the Lambda function role has Bedrock access
   aws iam put-role-policy \
     --role-name shoeshine-lambda-role \
     --policy-document '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": "bedrock:InvokeModel",
           "Resource": "arn:aws:bedrock:us-east-1:123456789012:model/*",
           "Condition": {
             "StringEquals": {
               "aws:SourceVpc": "arn:aws:ec2:123456789012:vpc-12345678"
             }
           }
         }
       ]
     }'
   ```

---

## Terraform Templates

### `terraform/main.tf`
```hcl
provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
  description = "AWS region"
}

variable "environment" {
  default = "production"
  description = "Environment (development, staging, production)"
}

variable "docker_image" {
  description = "ECR image URI for Shoeshine"
}

variable "api_key" {
  description = "Shoesine API key for authentication"
}

# VPC
resource "aws_vpc" "shoeshine" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Project = "Shoesine"
    Environment = var.environment
  }
}

# ECR Repository
resource "aws_ecr_repository" "shoeshine" {
  name                 = "shoeshine-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  tags = {
    Project = "Shoesine"
    Environment = var.environment
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "shoeshine" {
  name = "shoeshine-cluster"

  tags = {
    Project = "Shoesine"
    Environment = var.environment
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "shoeshine" {
  family                   = "shoeshine"
  network_mode             = "awsvpc"
  requires_compatibilities = [
    {
      cpu    = "2048"
      memory = "4096"
    }
  ]

  container_definitions = {
    name = "shoeshine"
    image = var.docker_image
    cpu    = 2048
    memory = 4096

    environment = [
      {
        name  = "SHOESHINE_ENV"
        value = var.environment
      },
      {
        name  = "SHOESHINE_API_KEY"
        value = var.api_key
      }
    ]

    log_configuration = {
      log_driver = "awslogs"
      options = {
        "awslogs-group" = "/aws/shoeshine"
        "awslogs-region" = var.aws_region
      }
    }
  }

  tags = {
    Project = "Shoesine"
    Environment = var.environment
  }
}

# ECS Service
resource "aws_ecs_service" "shoeshine_api" {
  name            = "shoeshine-api"
  cluster         = aws_ecs_cluster.shoeshine.id
  task_definition = aws_ecs_task_definition.shoeshine.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  platform_version = "LATEST"

  network_configuration {
    subnets = aws_subnet.shoeshine_public[*].id
    security_groups = [aws_security_group.shoeshine.id]
  }

  force_new_deployment = true

  tags = {
    Project = "Shoesine"
    Environment = var.environment
  }
}

# Security Group
resource "aws_security_group" "shoeshine" {
  name        = "shoeshine-api"
  description = "HTTP traffic to Shoeshine API"
  vpc_id      = aws_vpc.shoeshine.id

  ingress {
    from_port = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port = 0
    to_port   = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "Shoesine"
    Environment = var.environment
  }
}

# Outputs
output "api_endpoint" {
  description = "API endpoint URL"

  value = aws_lb.shoeshine.dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value = aws_ecs_cluster.shoeshine.name
}

output "task_definition_arn" {
  description = "ECS task definition ARN"
  value = aws_ecs_task_definition.shoeshine.arn
}
```

### `terraform/variables.tf`
```hcl
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "docker_image" {
  type    = string
  description = "ECR image URI for Shoeshine (e.g., 123456789012.dkr.ecr.us-east-1.amazonaws.com/shoeshine-api:latest)"
}

variable "api_key" {
  type      = string
  default   = ""
  sensitive = true
  description = "Secure API key for Shoeshine API authentication"
}

variable "enable_bedrock" {
  type    = bool
  default = false
  description = "Enable Bedrock integration for /harvest endpoint"
}
```

### `terraform/outputs.tf`
```hcl
output "api_endpoint" {
  description = "Public API endpoint URL"
  value = aws_lb.shoeshine.dns_name
}

output "ecs_service_name" {
  description = "ECS service name"
  value = aws_ecs_service.shoeshine_api.name
}

output "cluster_arn" {
  description = "ECS cluster ARN"
  value = aws_ecs_cluster.shoeshine.arn
}
```

---

## Manual Deployment Steps

### 1. Prepare Local Environment
```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure
# AWS Access Key ID: [YOUR_ACCESS_KEY_ID]
# AWS Secret Access Key: [YOUR_SECRET_ACCESS_KEY]
# Default region name: default

# Verify connection
aws sts get-caller-identity
```

### 2. Prepare Docker Image
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login -u AWS --password-stdin \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t shoeshine .

# Tag image
docker tag shoeshine <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine:latest

# Push image
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine:latest
```

### 3. Deploy with Terraform
```bash
# Initialize Terraform
terraform init

# Review plan
terraform plan -var-file=terraform.tfvars

# Deploy
terraform apply -var-file=terraform.tfvars

# Get outputs
terraform output
```

### 4. Test Deployment
```bash
# Get API endpoint
API_ENDPOINT=$(terraform output api_endpoint)

# Health check
curl $API_ENDPOINT/health

# Extract text from document (replace with base64)
curl -X POST $API_ENDPOINT/extract/text \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"document": "base64-encoded-image-here"}'

# With file upload
curl -X POST $API_ENDPOINT/extract/text \
  -H "X-API-Key: your-api-key-here" \
  -F "document=@path/to/document.jpg"
```

---

## Troubleshooting

### Docker Won't Start
```bash
# Check logs
docker logs <container-name>

# Check if port is already in use
netstat -tuln | grep 8000

# Check memory usage
docker stats
```

### Lambda Timeout
```bash
# Increase timeout if needed
aws lambda update-function-configuration \
  --function-name shoeshine-api \
  --timeout 300
```

### Bedrock Access Denied
```bash
# Verify IAM role has Bedrock permission
aws iam get-role-policy --role-name shoeshine-lambda-role

# Add Bedrock policy if needed
aws iam put-role-policy \
  --role-name shoeshine-lambda-role \
  --policy-document @bedrock-policy.json
```

### High Latency
```bash
# Check ECS task health
aws ecs describe-tasks --cluster shoeshine-cluster

# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimension-name ServiceName \
  --statistics SampleCount,Average,Maximum

# Increase task size if needed
aws ecs update-service \
  --cluster shoeshine-cluster \
  --service shoeshine-api \
  --task-definition shoeshine \
  --desired-count 2
```

---

## Security Best Practices

1. **Use API Keys**: Generate secure API keys for production
2. **Enable HTTPS**: Use Application Load Balancer with SSL certificates
3. **VPC Isolation**: Deploy in private VPC subnets
4. **Least Privilege IAM**: Only grant necessary permissions
5. **Enable Logging**: Use CloudWatch for all services
6. **Regular Updates**: Keep dependencies and base image updated
7. **Monitoring**: Set up CloudWatch alarms for:
   - CPU utilization
   - Memory utilization
   - 5XX errors
   - Lambda errors

---

## Cost Estimation

| Option | Instance Type | Monthly Cost |
|--------|-------------|------------|
| EC2 | t3.medium (2 vCPU, 4GB RAM) | $25-30 |
| ECS Fargate | 1 vCPU, 4GB RAM | $15-25 |
| Lambda (serverless) | Pay per request | $5-15 |

### Additional Costs
- Data transfer: ~$0.02-0.05/GB
- ECR storage: ~$0.10/GB/month
- CloudWatch Logs: ~$0.50/GB ingested
- Application Load Balancer: ~$20/month (optional)

---

## Next Steps

After deployment:
1. Configure DNS (Route 53) to point to your API endpoint
2. Set up monitoring and alerting
3. Configure CI/CD pipeline for future updates
4. Document API keys and management procedures

---

## Support

For issues or questions:
1. Check AWS CloudWatch logs
2. Review GitHub Issues
3. Consult AWS Documentation

---

## Useful Commands

```bash
# Get ECS logs
aws logs /aws/ecs/shoeshine --since 1h

# Update ECS service
aws ecs update-service --cluster shoeshine-cluster --service shoeshine-api --force-new-deployment

# Scale ECS service
aws ecs update-service --cluster shoeshine-cluster --service shoeshine-api --desired-count 5

# Get Lambda logs
aws logs --function-name shoeshine-api --tail

# Clean up old ECS images
aws ecr list-images --repository-name shoeshine-api
```
