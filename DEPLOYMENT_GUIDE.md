# Shoeshine Deployment Guide

## Deployment Options

### Option 1: AWS Lambda (Recommended for cost)

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
SHOESHINE_DEFAULT_OCR_ENGINE=auto          # auto: textract → easyocr
SHOESHINE_API_KEY=your-api-key
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250507
AWS_REGION=us-east-1
```

---

### Option 2: AWS ECS Fargate (Full OCR support)

**Supported OCR Engines:**
- AWS Textract (pay-per-request)
- EasyOCR (free)
- Docling (free, full document parsing)
- Tesseract (free, system dependency)

**Build & Deploy via Bamboo:**
```bash
# Build ECS container (includes all OCR engines)
docker build -f Dockerfile -t shoeshine-ecs:latest .

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
SHOESHINE_DEFAULT_OCR_ENGINE=docling       # or: auto, easyocr, textract, tesseract
SHOESHINE_API_KEY=your-api-key
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250507
AWS_REGION=us-east-1
```

---

## Bamboo Pipeline Configuration

### Lambda Deployment Stage
```yaml
# bamboo-specs/bamboo.yml
---
stages:
  - name: Build and Push Lambda
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

### ECS Deployment Stage
```yaml
# bamboo-specs/bamboo.yml
---
stages:
  - name: Build and Push ECS
    jobs:
      - name: ECS Build
        tasks:
          - script: |
              docker build -f Dockerfile -t shoeshine-ecs:latest .
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

| Use Case | Recommended Engine | Reason |
|----------|-------------------|--------|
| Simple scanned documents | Textract | Reliable, pay-per-use |
| High volume, cost-sensitive | EasyOCR | Free, runs locally |
| Complex PDFs with layout | Docling | Best structure extraction |
| Legacy documents | Tesseract | Mature, well-supported |
| Benchmarking | Multiple engines | Use `auto` or swap per request |

### API Usage by Engine
```bash
# Lambda (auto: textract → easyocr)
curl -X POST "http://api/extract/text" -F "document=@doc.pdf"

# Force specific engine (works in ECS, fails in Lambda for docling/tesseract)
curl -X POST "http://api/extract/text?ocr_engine=docling" -F "document=@doc.pdf"

# Check available engines
curl -X GET http://api/admin/ocr/status
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

*Note: ECS costs vary by region and usage pattern. Add Textract costs if using it.*

---

## Recommendations

1. **Start with Lambda** - Lower cost, simpler operations
2. **Use Textract** - Reliable, no cold start for OCR
3. **Switch to ECS only if needed** - When Docling/Tesseract required
4. **Benchmark with `auto` mode** - Let system choose best engine
