# Shoeshine Deployment Guide
# Region: eu-west-2 (London)

---

## ⚡️ Quick Summary

| Deployment | OCR Engines | Monthly Cost | Why This Default? |
|------------|-------------|--------------|-------------------|
| **Lambda (Default)** | Textract, EasyOCR | ~$29.00 | Cost-effective, auto-scales |
| **ECS (Optional)** | All 4 engines | ~$46.00 | Full OCR when needed |

**Recommendation:** Start with Lambda. Switch to ECS only when you need Docling/Tesseract.

---

## 🎯 Framework Design

This deployment is designed as a **model swapping framework** for both OCR and LLM:

### OCR Engine Swapping (Implemented ✅)
```bash
# Per-request engine selection
curl -X POST "http://api/extract/text?ocr_engine=textract" -F "document=@doc.pdf"
curl -X POST "http://api/extract/text?ocr_engine=easyocr" -F "document=@doc.pdf"

# Available engines depend on deployment mode
GET /admin/ocr/status  # Shows available engines
```

### LLM Model Swapping (Same Pattern - Coming Soon)
```json
{
  "document": "base64...",
  "question": "Summarize this",
  "llm_model": "anthropic.claude-sonnet-4-20250507"
}
```

**Benefits of this framework:**
- No redeployment needed to change models
- Easy A/B testing and benchmarking
- Per-request selection or global default
- Fallback chains for reliability

---

## Deployment Modes

### Mode 1: Lambda (Default - Lightweight)

**Use when:** You want simple, cost-effective deployment
- **OCR Engines:** Textract + EasyOCR only
- **Cost:** ~$29.00/month for 10K requests (eu-west-2)
- **Setup:** Minimal, no infrastructure management
- **Auto-scaling:** ✅ Yes (Lambda handles this)

**Why this is the default:**
1. **Cost-effective:** Pay per request, no idle costs
2. **Low maintenance:** No server management
3. **Auto-scales:** Handles traffic spikes automatically
4. **Sufficient for most cases:** Textract + EasyOCR cover 95% of use cases

### Mode 2: ECS (Full OCR - All Engines)

**Use when:** You need Docling or Tesseract
- **OCR Engines:** Textract + EasyOCR + Docling + Tesseract
- **Cost:** ~$46.00/month (24/7, eu-west-2)
- **Setup:** Requires ECS cluster, load balancer
- **Auto-scaling:** ⚠️ Manual configuration needed

**Why ECS is NOT the default:**

| Concern | Impact | Mitigation |
|---------|--------|------------|
| **Cost** | $46/mo vs $29/mo (58% more) | Only enable when needed |
| **Always On** | Pays even when idle | Lambda scales to zero |
| **Complexity** | More infrastructure | ECS cluster + ALB required |
| **Performance** | No cold starts | Lambda has ~5s cold start |

**When to enable ECS:**
- Need Docling for complex PDF structure extraction
- Tesseract gives better results on legacy documents
- Running benchmarks across all 4 engines
- High-volume, consistent traffic (no idle periods)

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
docker tag shoeshine-lambda:latest ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-2.amazonaws.com/shoeshine:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-2.amazonaws.com/shoeshine:latest

# Update Lambda (Bamboo task)
aws lambda update-function-code \
  --function-name shoeshine \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-2.amazonaws.com/shoeshine:latest
```

**Environment Variables:**
```
SHOESHINE_DEPLOY_MODE=lambda
SHOESHINE_DEFAULT_OCR_ENGINE=auto          # auto: textract → easyocr
SHOESHINE_API_KEY=your-api-key
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250507
AWS_REGION=eu-west-2
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

**⚠️ Cost & Performance Notes:**
- ECS runs 24/7 even with no traffic (~$46/mo)
- Lambda scales to zero (no idle cost)
- Consider testing Docling locally before enabling ECS
- See "Why ECS is NOT the default" section above

**Enable ECS when:**
1. You've tested Docling locally and it meets your needs
2. You need Tesseract for legacy document processing
3. Running benchmarks across all OCR engines
4. High-volume, consistent traffic justifies the cost

**Build & Deploy via Bamboo:**
```bash
# Build ECS container (includes all OCR engines)
docker build -f Dockerfile.ecs -t shoeshine-ecs:latest .

# Push to ECR
docker tag shoeshine-ecs:latest ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-2.amazonaws.com/shoeshine-ecs:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.eu-west-2.amazonaws.com/shoeshine-ecs:latest

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
AWS_REGION=eu-west-2
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

## Cost Comparison (eu-west-2)

### Lambda (per month, estimated 10K requests)
| Component | Cost |
|-----------|------|
| Lambda invocations | ~$1.00 |
| Lambda duration (3s avg) | ~$10.00 |
| Textract (text detection) | ~$1.50 |
| Bedrock (Q&A) | ~$15.00 |
| **Total** | **~$27.50/month** |

### ECS Fargate (per month, 24/7)
| Component | Cost |
|-----------|------|
| ECS Fargate (1GB, 0.5 vCPU) | ~$22.00 |
| ALB (load balancer) | ~$24.00 |
| Bedrock (Q&A) | ~$15.00 |
| **Total** | **~$61.00/month** |

*Note: Costs are estimates for eu-west-2 (London). Actual costs may vary based on usage.*

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

## 🎯 Model Swapping Framework

This implementation follows a **model swapping framework** pattern that can be applied to both OCR and LLM:

### Pattern: Per-Request Model Selection

```json
// OCR selection
POST /extract/text?ocr_engine=textract

// LLM selection (future implementation)
POST /harvest?llm_model=anthropic.claude-sonnet-4-20250507
```

### Framework Benefits

| Benefit | Description |
|---------|-------------|
| **No Redeployment** | Change models without redeploying |
| **Easy Benchmarking** | A/B test different models per request |
| **Per-Request Control** | Each request can use different models |
| **Fallback Chains** | System tries multiple models on failure |
| **Unified Interface** | Same API for all OCR/LLM providers |

### Current Implementation (OCR ✅)

```bash
# Available engines in Lambda mode
GET /admin/ocr/status
{
  "available_engines": ["textract", "easyocr"],
  "current_engine": "textract"
}

# Per-request selection
curl -X POST "http://api/extract/text?ocr_engine=textract" -F "document=@doc.pdf"
```

### Future Implementation (LLM 🔄)

Following the same pattern:

```json
POST /harvest {
  "document": "base64...",
  "question": "Summarize this",
  "llm_model": "anthropic.claude-sonnet-4-20250507"  // Per-request selection
}

# Or use global default
GET /admin/llm/status  // Shows available LLM models
```

---

## Recommendations

1. **Start with Lambda** - Lower cost, simpler operations
2. **Use `auto` mode** - System picks best available engine
3. **Test Docling locally** before enabling ECS (costs $46/mo extra)
4. **Benchmark with ECS** - Compare all 4 engines when needed
5. **Apply same pattern to LLM** - Following OCR swapping design

### When to Switch to ECS
- Need Docling for complex PDF parsing
- Want to compare all OCR engines
- Running legacy document workloads
- Tesseract gives better results for your documents
