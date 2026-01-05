# Shoeshine Deployment Guide

This guide provides detailed instructions for deploying Shoeshine to AWS using Terraform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [AWS Account Setup](#aws-account-setup)
3. [Building the Lambda Container](#building-the-lambda-container)
4. [Terraform Deployment](#terraform-deployment)
5. [Testing the Deployment](#testing-the-deployment)
6. [Monitoring and Logging](#monitoring-and-logging)
7. [Cleanup](#cleanup)

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **AWS CLI** (v2.x) - [Install guide](https://aws.amazon.com/cli/)
- **Terraform** (v1.0+) - [Install guide](https://www.terraform.io/downloads)
- **Docker** - [Install guide](https://docs.docker.com/get-docker/)
- **Python** (3.11+) - For local testing

### AWS Credentials

Ensure your AWS credentials are configured:

```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-west-1"
```

---

## AWS Account Setup

### 1. Create ECR Repository

```bash
# Create ECR repository for Lambda image
aws ecr create-repository \
  --repository-name shoeshine \
  --image-scanning-configuration scanOnPush=true
```

### 2. Enable Bedrock Access

Ensure Bedrock is available in your region and you have access:

```bash
# Check available Bedrock models
aws bedrock list-foundation-models --region eu-west-1
```

> **Note:** The following sections describe optional Terraform backend configuration for team deployments.
> For single-user deployments, Terraform's local state backend is sufficient.
> Skip to [Building the Lambda Container](#building-the-lambda-container) if deploying alone.

### 3. (Optional) Create S3 Bucket for Terraform State

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://shoeshine-terraform-state

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket shoeshine-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket shoeshine-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### 4. (Optional) Create DynamoDB Table for Terraform Lock

```bash
aws dynamodb create-table \
  --table-name shoeshine-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

---

## Building the Lambda Container

### 1. Build the Docker Image

```bash
# Build the Lambda container image
docker build -f Dockerfile.lambda -t shoeshine-lambda .
```

### 2. Test Locally (Optional)

```bash
# Run container locally
docker run -p 8080:8080 shoeshine-lambda

# Test with curl
curl http://localhost:8080/health
```

### 3. Push to ECR

```bash
# Get login password
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.eu-west-1.amazonaws.com

# Tag the image
docker tag shoeshine-lambda:latest \
  <account-id>.dkr.ecr.eu-west-1.amazonaws.com/shoeshine:latest

# Push to ECR
docker push <account-id>.dkr.ecr.eu-west-1.amazonaws.com/shoeshine:latest
```

### 4. Note the Image URI

```
<account-id>.dkr.ecr.eu-west-1.amazonaws.com/shoeshine:latest
```

---

## Terraform Deployment

### API Gateway Type

This deployment uses **API Gateway v2 (HTTP API)** which provides:
- Lower cost: $1.00 per 1M requests
- Built-in CORS support
- Simpler setup
- Better performance

If you need REST API v1 features (custom authorizers, WAF integration, etc.), modify `terraform/main.tf` line 226:

```hcl
protocol_type = "HTTP"  # Current (HTTP API v2)
# protocol_type = "REST"  # Alternative (REST API v1, $3.50 per 1M requests)
```

### 1. Initialize Terraform

```bash
cd terraform

# Initialize with S3 backend
terraform init
```

### 2. Create Terraform Variables

Create a `terraform.tfvars` file:

```hcl
# AWS Region
aws_region = "eu-west-1"

# Environment
environment = "production"

# API Key (generate with: openssl rand -base64 32)
api_key = "your-secure-api-key-here"

# Lambda Configuration
lambda_memory   = 2048
lambda_timeout  = 300
lambda_reserved_concurrency = 0

# Bedrock Model
bedrock_model_id = "anthropic.claude-sonnet-4-20250507"
enable_bedrock = true

# Optional: S3 bucket for document storage
# Leave empty to skip, or provide existing bucket name
s3_bucket = ""

# ECR Image Tag
ecr_image_tag = "latest"
```

### 3. Plan Deployment

```bash
terraform plan -out=tfplan
```

### 4. Apply Deployment

```bash
terraform apply tfplan
```

### 5. Get Outputs

```bash
# API Endpoint
terraform output api_endpoint

# Other outputs
terraform output lambda_function_name
terraform output s3_bucket_name
```

---

## Testing the Deployment

### 1. Get the API Endpoint

```bash
API_ENDPOINT=$(terraform output -raw api_endpoint)
echo "API Endpoint: $API_ENDPOINT"
```

### 2. Health Check

```bash
curl $API_ENDPOINT/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0",
  "environment": "production",
  "services": {
    "ocr": true,
    "bedrock": true,
    "storage": true
  }
}
```

### 3. Test Text Extraction

```bash
# Create a test image (1x1 pixel PNG)
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" | base64 -d > test.png

# Extract text
curl -X POST $API_ENDPOINT/extract/text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d "{\"document\": \"$(base64 -w 0 test.png)\"}"
```

### 4. Test Harvest Endpoint

```bash
# Test structured extraction
curl -X POST $API_ENDPOINT/harvest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "document": "<base64-encoded-image>",
    "fields": ["total", "date", "vendor"]
  }'
```

### 5. Load Test (Optional)

```bash
# Install hey (HTTP load tester)
go install github.com/rakyll/hey@latest

# Run load test
hey -n 100 -c 10 \
  -H "X-API-Key: your-api-key" \
  -m POST \
  -d '{"document": "<base64-encoded-image>"}' \
  "$API_ENDPOINT/extract/text"
```

---

## Monitoring and Logging

### 1. CloudWatch Logs

View logs in CloudWatch Console:
```
AWS Console > CloudWatch > Log groups > /aws/lambda/shoeshine-*
```

### 2. CloudWatch Metrics

View metrics in CloudWatch Console:
```
AWS Console > CloudWatch > Metrics > All metrics > Lambda
```

Key metrics:
- Invocations
- Errors
- Duration
- Throttles

### 3. X-Ray Tracing (Optional)

If enabled, view traces:
```
AWS Console > X-Ray > Service map
```

### 4. API Gateway Metrics

```
AWS Console > API Gateway > Your API > Stage > Metrics
```

---

## Security Best Practices

### 1. API Key Management

- Use a strong, random API key
- Rotate keys regularly
- Store keys in AWS Secrets Manager

```bash
# Store API key in Secrets Manager
aws secretsmanager create-secret \
  --name shoeshine/api-key \
  --secret-string "your-api-key"
```

### 2. IAM Roles

The Terraform configuration creates minimal IAM roles with least privilege:
- Bedrock access (read-only)
- S3 access (specific bucket)
- DynamoDB access (specific table)
- CloudWatch Logs access

### 3. API Gateway Throttling

Default throttling:
- Burst limit: 100 requests/second
- Rate limit: 1000 requests/second

### 4. VPC Configuration

For private deployment, configure VPC:
```hcl
# Add to main.tf
resource "aws_security_group" "lambda" {
  name        = "shoeshine-lambda-sg"
  description = "Security group for Lambda function"
  vpc_id      = "your-vpc-id"

  # No inbound rules - Lambda is triggered by API Gateway
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

---

## Cleanup

### 1. Destroy Terraform Resources

```bash
cd terraform
terraform destroy
```

This will remove:
- Lambda function
- API Gateway
- CloudWatch log groups
- IAM roles and policies
- ECR repository
- S3 bucket (if created by Terraform)

### 2. Delete ECR Repository (if not destroyed by Terraform)

```bash
aws ecr delete-repository \
  --repository-name shoeshine \
  --force
```

### 3. Delete S3 Bucket (if using external bucket)

```bash
# Empty and delete S3 bucket (if you created one manually)
aws s3 rb s3://your-bucket-name --force
```


---

## Troubleshooting

### Lambda Cold Starts

EasyOCR and Tesseract can cause cold starts (15-30s for first invocation). Mitigate with:

1. **Increased Memory** (faster CPU, no extra cost for cold starts)
   ```hcl
   lambda_memory = 3072  # or 4096
   ```

2. **Pre-downloaded Models** (already in Dockerfile.lambda)
   - EasyOCR models are pre-downloaded during build
   - Reduces cold start by ~3 minutes

3. **Keep Warm with Scheduled Pings** (not recommended for low traffic)
   - Schedule CloudWatch Event to invoke Lambda every 5 minutes

### Lambda Timeout Errors

If Lambda times out before completing OCR:

1. **Increase timeout** (max 900s)
   ```hcl
   lambda_timeout = 300  # or higher for large documents
   ```

2. **Increase memory** (faster processing)
   ```hcl
   lambda_memory = 3072
   ```

### OCR Not Available

Check CloudWatch logs for errors:
- Missing dependencies
- Memory issues
- Timeout configuration

### Bedrock Access Denied

Verify IAM role has Bedrock permissions:
```bash
aws bedrock list-foundation-models --region eu-west-1
```

### API Returns 403

Check:
- API key is correct
- API key is set in Terraform variables
- Request includes `X-API-Key` header

---

## Cost Estimation

| Service | Approximate Cost (eu-west-1) |
|---------|------------------------------|
| Lambda | $0.20 per 1M requests + compute |
| API Gateway (REST API) | $3.50 per 1M API calls |
| S3 | $0.023 per GB/month |
| ECR Storage | $0.10 per GB/month |
| CloudWatch Logs | $0.50 per GB ingested |
| Bedrock | $0.03 per 1K input tokens (Claude) |

**Estimated cost for 1M requests/month:**
- Lambda (2048MB, 5s duration): ~$100
- API Gateway (REST API): ~$3.50
- ECR Storage (3GB): ~$0.30
- Bedrock (structured extraction): ~$50
- CloudWatch Logs: ~$10
- **Total: ~$164/month**

**Note: Lambda costs scale with usage - you pay nothing when not in use!**

---

## Support

- GitHub Issues: https://github.com/yourusername/shoeshine/issues
- Documentation: See README.md
