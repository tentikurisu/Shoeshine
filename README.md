# Shoeshine - AWS-Only Deployment

**Document scanning layer for AWS Bedrock with Lambda deployment.**

---

## ⚠️ aws-bedrock-only Branch

This is a **separate development line** from the main Shoeshine repository. It is designed for AWS-only deployment with:
- EasyOCR running in AWS Lambda
- AWS Bedrock for LLM (no Ollama)
- S3 for document retrieval (existing buckets only)

**This branch is NOT intended to be merged back into main.**

---

## What is Shoeshine?

Shoeshoe extracts text from images and PDFs using OCR, then sends the extracted text to AWS Bedrock for Q&A. It is **not an LLM itself** - it is a document-to-text translator.

### Key Features

| Feature | Description |
|---------|-------------|
| **EasyOCR in Lambda** | OCR runs inside AWS Lambda container |
| **Bedrock Integration** | Sends extracted text to AWS Bedrock for Q&A |
| **S3 Document Retrieval** | Read documents from existing S3 buckets |
| **API Gateway** | HTTP endpoint via AWS API Gateway |
| **No Local Services** | 100% AWS-native, no Ollama or local dependencies |

---

## Architecture

```
Document (base64 or S3)
        ↓
┌─────────────────────────────────────┐
│  AWS API Gateway                    │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  AWS Lambda (Container)             │
│  ├── EasyOCR (OCR extraction)       │
│  ├── FastAPI (HTTP handler)         │
│  └── BedrockClient (LLM calls)      │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  AWS Bedrock                        │
│  (Non-vision models: Claude, etc.)  │
└─────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- AWS CLI installed and configured
- Docker installed
- Terraform installed
- AWS account with Bedrock access enabled

### Configuration

1. Copy Terraform variables:
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars`:
```hcl
aws_region   = "us-east-1"
environment  = "production"
api_key      = "your-generated-api-key"
bedrock_model_id = "anthropic.claude-sonnet-4-20250507"
allowed_s3_buckets = "corp-docs,bucket-name"
```

### Deployment

```bash
# Build Lambda image
docker build -f Dockerfile.lambda -t shoeshine-lambda:latest .

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag shoeshine-lambda:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shoeshine:latest

# Deploy infrastructure
cd terraform
terraform init
terraform apply
```

### Testing

```bash
# Get API endpoint
API_ENDPOINT=$(terraform output -raw api_endpoint)

# Health check
curl $API_ENDPOINT/health

# Harvest endpoint (extract + Bedrock Q&A)
curl -X POST $API_ENDPOINT/harvest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"document": "<base64-image>", "question": "Summarize this"}'

# Or with S3 document
curl -X POST $API_ENDPOINT/harvest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"s3_bucket": "bucket-name", "s3_key": "doc.pdf", "question": "What is the total?"}'
```

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/extract/text` | Extract plain text from document |
| POST | `/extract/bbox` | Extract text with bounding boxes |
| POST | `/harvest` | Extract text + Bedrock Q&A |

### Authentication

All endpoints accept `X-API-Key` header. Configure via `SHOESHINE_API_KEY` environment variable.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SHOESHINE_API_KEY` | Yes | - | API key for authentication |
| `AWS_REGION` | No | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | Yes | - | Bedrock model ID (e.g., anthropic.claude-sonnet-4-20250507) |
| `ALLOWED_S3_BUCKETS` | No | `` | Comma-separated S3 buckets |

---

## Project Structure

```
shoeshine/
├── api_server.py              # Main API server (FastAPI)
├── Dockerfile.lambda          # Lambda container image
├── docker-compose.yml         # Local testing
├── config.yaml                # Configuration
├── requirements.txt           # Python dependencies
├── terraform/                 # AWS infrastructure
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── src/                       # Source code
│   ├── llm_clients.py         # BedrockClient
│   ├── config.py
│   └── services/
├── examples/                  # Integration examples
│   ├── bedrock_integration.py
│   └── basic_usage.py
└── tests/                     # Test suite
```
