# Shoeshine - AWS-Only Deployment

**Document scanning layer for AWS Bedrock with Lambda deployment.**

**Model Swapping Framework:** This implementation supports easy OCR and LLM model selection via API requests - no redeployment needed.

---

## ⚡️ Quick Start

### Default Deployment (Lambda - Cost Effective)
- **Cost:** ~$29/month
- **OCR Engines:** Textract, EasyOCR
- **Auto-scales:** Yes

### Optional: Full OCR (ECS - Additional Cost)
- **Cost:** ~$46/month (24/7)
- **OCR Engines:** Textract, EasyOCR, Docling, Tesseract
- **Enable when:** Need Docling or Tesseract

---

## Deployment Modes

| Mode | Engines | Monthly Cost | When to Use |
|------|---------|--------------|-------------|
| **Lambda (Default)** | Textract, EasyOCR | ~$29 | General purpose, cost-sensitive |
| **ECS (Optional)** | All 4 engines | ~$46 | Complex PDFs, legacy docs |

**Why Lambda is default:**
- Pay-per-request (no idle costs)
- Auto-scales to handle traffic
- Simple infrastructure

**Why ECS is optional:**
- Runs 24/7 (even when idle)
- More complex infrastructure
- Only needed for Docling/Tesseract

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
aws_region   = "eu-west-2"
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
aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-2.amazonaws.com
docker tag shoeshine-lambda:latest <account-id>.dkr.ecr.eu-west-2.amazonaws.com/shoeshine:latest
docker push <account-id>.dkr.ecr.eu-west-2.amazonaws.com/shoeshine:latest

# Deploy infrastructure
cd terraform
terraform init
terraform apply
```

### Testing Docling Locally (Before Enabling ECS)

Docling is NOT included in Lambda deployment due to size constraints. Test it locally first:

```bash
# Install docling locally
pip install docling

# Test with sample document
python -c "
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
result = converter.convert('your-document.pdf')
print(result.document.export_to_text())
```

If Docling meets your needs, enable ECS deployment (additional $46/mo).

---

## Model Swapping Framework

This implementation supports easy **per-request model selection** - no redeployment needed:

### OCR Engine Selection
```bash
# Use default (auto: tries textract → easyocr)
curl -X POST "$API_ENDPOINT/extract/text" -F "document=@doc.pdf"

# Force specific engine
curl -X POST "$API_ENDPOINT/extract/text?ocr_engine=textract" -F "document=@doc.pdf"
curl -X POST "$API_ENDPOINT/extract/text?ocr_engine=easyocr" -F "document=@doc.pdf"

# Check available engines
curl "$API_ENDPOINT/admin/ocr/status"
```

### Available Engines by Deployment

| Deployment | Engines |
|------------|---------|
| Lambda (Default) | textract, easyocr |
| ECS (Optional) | textract, easyocr, docling, tesseract |

### Benefits
- **No Redeployment:** Change engines without infrastructure changes
- **Easy Benchmarking:** Test different engines per request
- **Fallback Chain:** System tries multiple engines on failure
- **Cost Control:** Use cheaper engines by default

### Same Pattern for LLM (Future)
Following this framework for LLM model selection:
```json
POST /harvest {
  "document": "base64...",
  "question": "Summarize this",
  "llm_model": "anthropic.claude-sonnet-4-20250507"
}
```

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/admin/ocr/status` | OCR engine status |
| POST | `/admin/ocr/unload` | Unload current engine |
| POST | `/extract/text` | Extract plain text from document |
| POST | `/extract/bbox` | Extract text with bounding boxes |
| POST | `/harvest` | Extract text + Bedrock Q&A |

### Authentication

All endpoints accept `X-API-Key` header. Configure via `SHOESHINE_API_KEY` environment variable.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SHOESHINE_API_KEY` | Yes | - | API key for authentication |
| `AWS_REGION` | No | `eu-west-2` | AWS region |
| `BEDROCK_MODEL_ID` | Yes | - | Bedrock model ID (e.g., anthropic.claude-sonnet-4-20250507) |
| `SHOESHINE_DEFAULT_OCR_ENGINE` | No | `auto` | Default OCR engine |
| `SHOESHINE_DEPLOY_MODE` | No | `lambda` | Deployment mode (lambda/ecs) |
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
