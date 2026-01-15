# Shoeshine Deployment Guide

## Deployment Modes

### Mode 1: Lambda (Default - Lightweight)
**Use when:** You want simple, cost-effective deployment
- **OCR Engines:** Textract + EasyOCR only
- **Cost:** ~$26.50/month for 10K requests
- **Setup:** Minimal, no infrastructure management

### Mode 2: ECS (Full OCR - All Engines)
**Use when:** You need Docling or Tesseract
- **OCR Engines:** Textract + EasyOCR + Docling + Tesseract
- **Cost:** ~$35.00/month (24/7)
- **Setup:** Requires ECS cluster, load balancer

---

## Quick Toggle

Set this in Bamboo or environment to switch modes:

| Variable | Lambda (Default) | ECS (Full OCR) |
|----------|------------------|----------------|
| `SHOESHINE_DEPLOY_MODE` | `lambda` | `ecs` |
| `SHOESHINE_DEFAULT_OCR_ENGINE` | `auto` | `docling` |

```bash
# Lambda mode (default)
export SHOESHINE_DEPLOY_MODE=lambda
export SHOESHINE_DEFAULT_OCR_ENGINE=auto

# ECS mode (full OCR)
export SHOESHINE_DEPLOY_MODE=ecs
export SHOESHINE_DEFAULT_OCR_ENGINE=docling
```

---

## Lambda Deployment (Default)

**Supported OCR Engines:**
- AWS Textract (pay-per-request)
- EasyOCR (free, pre-loaded in container)

**Build & Deploy via Bamboo:**
```bash
# Build Lambda container
docker build -f Dockerfile.lambda -t shoeshine-lambda:latest .

# Push to ECR
docker tag shoeshine-lambda:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/shoeshine:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/shoeshine:latest

# Update Lambda (Bamboo task)
aws lambda update-function-code \
  --function-name shoeshine \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/shoeshine:latest
```

**Environment Variables:**
```
SHOESHINE_DEPLOY_MODE=lambda
SHOESHINE_DEFAULT_OCR_ENGINE=auto          # auto: textract → easyocr
SHOESHINE_API_KEY=your-api-key
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250507
AWS_REGION=us-east-1
```

---

## ECS Deployment (Full OCR - All Engines)

**Supported OCR Engines:**
- AWS Textract (pay-per-request)
- EasyOCR (free)
- Docling (free, full document parsing)
- Tesseract (free, system dependency)

**Why use ECS?**
- Docling provides better PDF structure extraction
- Tesseract handles legacy documents well
- Run benchmarks across all 4 engines
- No Lambda cold starts

**Build & Deploy via Bamboo:**
```bash
# Build ECS container (includes all OCR engines)
docker build -f Dockerfile.ecs -t shoeshine-ecs:latest .

# Push to ECR
docker tag shoeshine-ecs:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/shoeshine-ecs:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/shoeshine-ecs:latest

# Update ECS service (Bamboo task)
aws ecs update-service \
  --cluster shoeshine-cluster \
  --service shoeshine-service \
  --task-definition shoeshine-task
```

**Environment Variables:**
```
SHOESHINE_DEPLOY_MODE=ecs
SHOESHINE_DEFAULT_OCR_ENGINE=docling       # or: auto, easyocr, textract, tesseract
SHOESHINE_API_KEY=your-api-key
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250507
AWS_REGION=us-east-1
```

---

## Bamboo Pipeline Configuration

### Lambda Stage (Default)
```yaml
# bamboo-specs/bamboo.yml
---
stages:
  - name: Build Lambda
    jobs:
      - name: Lambda Build
        tasks:
          - script: |
              docker build -f Dockerfile.lambda -t shoeshine-lambda:latest .
              docker login --username AWS --password-stdin ${ECR_LOGIN}
              docker tag shoeshine-lambda:latest ${ECR_URL}:latest
              docker push ${ECR_URL}:latest
          - script: |
              aws lambda update-function-code \
                --function-name shoeshine \
                --image-uri ${ECR_URL}:latest
```

### ECS Stage (Toggle to Enable)
```yaml
# bamboo-specs/bamboo.yml
---
stages:
  - name: Build ECS (Full OCR)
    jobs:
      - name: ECS Build
        tasks:
          - script: |
              docker build -f Dockerfile.ecs -t shoeshine-ecs:latest .
              docker login --username AWS --password-stdin ${ECR_LOGIN}
              docker tag shoeshine-ecs:latest ${ECR_URL}-ecs:latest
              docker push ${ECR_URL}-ecs:latest
          - script: |
              aws ecs update-service \
                --cluster shoeshine-cluster \
                --service shoeshine-service \
                --task-definition shoeshine-task \
                --force-new-deployment
```

---

## OCR Engine Selection Guide

| Use Case | Recommended Engine | Deployment |
|----------|-------------------|------------|
| Simple scanned documents | Textract | Lambda or ECS |
| High volume, cost-sensitive | EasyOCR | Lambda or ECS |
| Complex PDFs with layout | Docling | ECS only |
| Legacy documents | Tesseract | ECS only |
| Benchmarking comparison | Multiple | ECS only |

### API Usage by Engine
```bash
# Lambda/ECS (auto: tries available engines)
curl -X POST "http://api/extract/text" -F "document=@doc.pdf"

# Force specific engine (fails if not available in current deployment)
curl -X POST "http://api/extract/text?ocr_engine=docling" -F "document=@doc.pdf"

# Check available engines
curl -X GET http://api/admin/ocr/status
{
  "current_engine": "textract",
  "available_engines": ["textract", "easyocr"],
  "is_lambda": true
}
```

---

## Cost Comparison

### Lambda (per month, estimated 10K requests)
| Component | Cost |
|-----------|------|
| Lambda invocations | ~$1.00 |
| Lambda duration (3s avg) | ~$9.00 |
| Textract (text detection) | ~$1.50 |
| Bedrock (Q&A) | ~$15.00 |
| **Total** | **~$26.50/month** |

### ECS Fargate (per month, 24/7)
| Component | Cost |
|-----------|------|
| ECS Fargate (1GB, 0.5 vCPU) | ~$20.00 |
| Bedrock (Q&A) | ~$15.00 |
| **Total** | **~$35.00/month** |

*Note: Add Textract costs if using it in ECS. ECS costs vary by region and usage.*

---

## Why Some Engines Are Lambda-Excluded

### Docling
- **Reason:** Heavy ML dependencies (torch, transformers) >250MB
- **Solution:** Use ECS for Docling support
- **Benefit:** Best-in-class PDF structure extraction

### Tesseract
- **Reason:** Requires system binaries, not available in Lambda runtime
- **Solution:** Use ECS for Tesseract support
- **Benefit:** Mature, reliable for legacy documents

---

## Recommendations

1. **Start with Lambda** - Lower cost, simpler operations
2. **Use `auto` mode** - System picks best available engine
3. **Switch to ECS when needed** - Set `SHOESHINE_DEPLOY_MODE=ecs`
4. **Benchmark with ECS** - Compare all 4 engines

### When to Switch to ECS
- Need Docling for complex PDF parsing
- Want to compare all OCR engines
- Running legacy document workloads
- Tesseract gives better results for your documents
