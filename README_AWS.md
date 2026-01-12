# Shoeshine AWS-Only Branch

**Branch**: `aws-bedrock-only`

This branch removes all local LLM (Ollama) dependencies and ships only AWS-native services:
- EasyOCR for document OCR (Lambda-based)
- AWS Bedrock for document Q&A
- S3 for document retrieval (existing buckets only, no bucket creation)

## What's Different

| Feature | Main Branch | AWS-Only Branch |
|---------|-------------|-----------------|
| OCR | EasyOCR/Tesseract | EasyOCR (Lambda) |
| LLM | Ollama (local) + Bedrock | Bedrock only |
| S3 | Create or use buckets | Use existing buckets only |
| Deployment | Docker/Lambda | Lambda + API Gateway |

## Quick Start

### Prerequisites

- AWS CLI installed and configured
- Docker installed locally
- Terraform installed
- AWS account with Bedrock access enabled

### Configuration

1. Configure AWS credentials:
```bash
aws configure
```

2. Copy Terraform variables:
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

3. Edit `terraform.tfvars`:
```hcl
aws_region   = "us-east-1"
environment  = "production"
api_key      = "your-generated-api-key"
bedrock_model_id = "anthropic.claude-sonnet-4-20250507"
allowed_s3_buckets = "corp-docs,team-bucket"
```

### Deployment

```bash
# Build Lambda image
docker build -f Dockerfile.lambda -t shoeshine-aws:latest .

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag shoeshine-aws:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine:latest

# Deploy infrastructure
terraform init
terraform apply
```

### Testing

```bash
# Get API endpoint
API_ENDPOINT=$(terraform output -raw api_endpoint)

# Health check
curl $API_ENDPOINT/health

# Test harvest with base64 document
curl -X POST $API_ENDPOINT/harvest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"document": "<base64-image>", "question": "Summarize this"}'

# Test harvest with S3 document
curl -X POST $API_ENDPOINT/harvest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"s3_bucket": "corp-docs", "s3_key": "invoice.pdf", "question": "What is the total?"}'
```

## API Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0",
  "services": {
    "ocr": true,
    "bedrock": true
  },
  "ocr_engine": "easyocr"
}
```

### POST /extract/text
Extract plain text from a document (base64-encoded image).

### POST /extract/bbox
Extract text with bounding box coordinates.

### POST /harvest
Extract text from document and send to Bedrock for Q&A.

**Request:**
```json
{
  "document": "<base64-encoded-image>",
  "question": "What is the total amount?",
  "prompt": "You are a financial document analyst. Extract exact amounts only.",
  "temperature": 0.0
}
```

Or with S3:

```json
{
  "s3_bucket": "corp-docs",
  "s3_key": "invoices/2024/inv-123.pdf",
  "question": "What is the total?",
  "prompt": "Answer based ONLY on the document."
}
```

**Response:**
```json
{
  "success": true,
  "extracted_text": "Invoice #12345...",
  "answer": "The total amount is $1,234.56",
  "model": "anthropic.claude-sonnet-4-20250507",
  "processing_time_ms": 5234.5
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SHOESHINE_API_KEY` | Yes | - | API key for authentication |
| `AWS_REGION` | No | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | No | `anthropic.claude-sonnet-4-20250507` | Bedrock model |
| `ALLOWED_S3_BUCKETS` | No | `` | Comma-separated S3 buckets |

## S3 Integration

The AWS-only branch supports reading documents from existing S3 buckets:

1. Configure allowed buckets in Terraform: `allowed_s3_buckets = "bucket1,bucket2"`
2. Lambda needs IAM permission: `s3:GetObject` on allowed buckets
3. Use the harvest endpoint with `s3_bucket` and `s3_key` parameters

No S3 buckets are created by this deployment. Use your existing buckets.

## Cleanup

```bash
cd terraform
terraform destroy
```

## Troubleshooting

### Bedrock access denied
- Ensure Bedrock is enabled in your AWS account
- Verify IAM permissions include `bedrock:InvokeModel`
- Check the model ID is available in your region

### S3 access denied
- Verify bucket is in `allowed_s3_buckets` list
- Check Lambda IAM role has `s3:GetObject` permission
- Ensure bucket exists and is accessible

### OCR not available
- Check CloudWatch logs for EasyOCR initialization errors
- Ensure Lambda has enough memory (2048MB+ recommended)
- First request may take 30+ seconds (cold start with model download)
