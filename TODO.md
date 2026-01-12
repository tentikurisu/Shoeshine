# Shoeshine AWS-Only Branch - Session Tracker

## Overview
This file tracks work sessions and future phases for the `aws-bedrock-only` branch. Use it to quickly understand what was done and what needs to be picked up in future sessions.

---

## Session 1 (COMPLETED ✓)
**Date**: Jan 12, 2026

### Completed Work
- Created `aws-bedrock-only` branch from main
- Replaced OllamaClient with BedrockClient (`src/llm_clients.py`)
- New harvest endpoint with S3 document retrieval (`api_server.py`)
- Added `allowed_s3_buckets` config option (`src/config.py`)
- Removed all Ollama integration files
- Updated examples (`bedrock_integration.py`) to use new harvest endpoint
- Cleaned up Terraform (no bucket creation, S3 access policy)
- Removed GitHub workflows (Bamboo handles deployment)
- Updated docker-compose.yml (no Ollama dependency)
- Created `README_AWS.md` documentation

### Files Changed
| File | Change |
|------|--------|
| `src/llm_clients.py` | Replaced OllamaClient with BedrockClient |
| `src/config.py` | Added `allowed_s3_buckets` option |
| `api_server.py` | New harvest endpoint, S3 support, removed Ollama |
| `config.yaml` | Removed Ollama section |
| `examples/bedrock_integration.py` | Updated for new harvest endpoint |
| `terraform/main.tf` | S3 access policy, no bucket creation |
| `terraform/variables.tf` | Added `allowed_s3_buckets` variable |
| `terraform/outputs.tf` | Removed S3 bucket output |
| `docker-compose.yml` | Removed Ollama, updated for local OCR testing |

### Files Removed
- `.github/workflows/` - Not needed (Bamboo handles deployment)
- `examples/ollama_integration.py` - Ollama not available in this branch

---

## Phase 2: Easy Model Swapping
**Status**: PENDING

### Goal
Make Bedrock model selection configurable at runtime via API request.

### Tasks
- [ ] Add `model` field to harvest endpoint request
- [ ] Support multiple Bedrock models:
  - [ ] Claude (Anthropic) - `anthropic.claude-sonnet-4-20250507`
  - [ ] Llama (Meta) - `meta.llama3-2-90b-instruct-v1:0`
  - [ ] Titan (Amazon) - `amazon.titan-text-premier-v1:0`
  - [ ] Jurassic (AI21) - `ai21.jamba-1-5-large-v1:0`
- [ ] Update BedrockClient to accept model_id parameter
- [ ] Add model selection to config.yaml
- [ ] Add available models to /models endpoint

### Example Request (After Implementation)
```json
{
  "document": "<base64>",
  "question": "Summarize this document",
  "model": "anthropic.claude-sonnet-4-20250507",
  "prompt": "You are a financial analyst..."
}
```

### Notes
- Keep default model as Claude Sonnet
- Validate model IDs against Bedrock available models
- Consider caching model list for /models endpoint

---

## Phase 3: Easy OCR Swapping
**Status**: PENDING

### Goal
Support multiple OCR engines with simple config swap.

### Tasks
- [ ] Create OCR factory pattern
- [ ] Add OCR engine selection to config:
  ```yaml
  ocr:
    engine: "easyocr"  # or "textract" or "docling"
  ```
- [ ] Integrate AWS Textract
- [ ] Integrate Docling (for better table preservation)
- [ ] Create unified OCR interface
- [ ] Add OCR benchmark tests
- [ ] Document trade-offs between engines

### OCR Engine Comparison
| Engine | Pros | Cons |
|--------|------|------|
| EasyOCR | Local, no AWS cost | Slower cold start |
| Textract | Native AWS, fast | Cost per document |
| Docling | Better tables | Requires investigation |

### Notes
- EasyOCR is currently hardcoded in api_server.py
- Need abstraction layer for OCR engines
- Textract requires additional IAM permissions

---

## Phase 4: Benchmarks
**Status**: PENDING

### Goal
Compare model performance, accuracy, and costs.

### Tasks
- [ ] Create benchmark suite (`tests/benchmarks/`)
- [ ] OCR accuracy comparison:
  - [ ] EasyOCR vs Textract vs Docling
  - [ ] Document type variations (receipts, invoices, forms)
- [ ] LLM quality comparison:
  - [ ] Response accuracy
  - [ ] Consistency
  - [ ] Prompt adherence
- [ ] Cost analysis:
  - [ ] Per-document cost by model
  - [ ] Monthly cost projections
- [ ] Latency metrics:
  - [ ] Cold start times
  - [ ] Processing time by document size
- [ ] Generate benchmark report

### Example Benchmark Result
| Model | Avg Latency | Cost/1K Docs | Accuracy |
|-------|-------------|--------------|----------|
| Claude Sonnet | 2.3s | $15.00 | 94% |
| Llama 3 | 1.8s | $8.00 | 89% |
| Titan | 1.5s | $5.00 | 85% |

---

## Quick Reference

### Current Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/extract/text` | Extract text from base64 image |
| POST | `/extract/bbox` | Extract text with bounding boxes |
| POST | `/harvest` | Extract + Bedrock Q&A with custom prompt |

### Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SHOESHINE_API_KEY` | Yes | - | API key for authentication |
| `AWS_REGION` | No | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | No | `anthropic.claude-sonnet-4-20250507` | Bedrock model |
| `ALLOWED_S3_BUCKETS` | No | `` | Comma-separated S3 buckets |

### Deploy via Bamboo
```bash
# Configure in Bamboo:
# - AWS credentials
# - Terraform variables
# - S3 backend for state
```

---

## Next Session Checklist

- [ ] Review current branch status: `git status`
- [ ] Test locally (optional):
  ```bash
  export AWS_REGION=us-east-1
  export AWS_ACCESS_KEY_ID=xxx
  export AWS_SECRET_ACCESS_KEY=xxx
  docker-compose up --build
  ```
- [ ] Deploy via Bamboo if ready
- [ ] Pick up next phase (2, 3, or 4)

---

## Notes
- Branch: `aws-bedrock-only`
- Main deployment: Bamboo (Bitbucket)
- Terraform state: S3 backend (configure in Bamboo)
- No local LLM required (Bedrock only)
