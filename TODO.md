# Shoeshine AWS-Only Branch - Session Tracker

## Overview
This file tracks work sessions and future phases for the `feature/ocr-model-swapping` branch. Use it to quickly understand what was done and what needs to be picked up in future sessions.

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
- `src/local_harvest.py` - Replaced by Bedrock
- `test_setup.py` - Tested Ollama, not needed

---

## Session 2 (COMPLETED ✓)
**Date**: Jan 15, 2026

### Completed Work
- Created `feature/ocr-model-swapping` branch from `aws-bedrock-only`
- Implemented OCR model swapping framework (per-request engine selection)
- Added 4 OCR engines: Textract, EasyOCR, Docling, Tesseract
- Created OCRServiceFactory with single active engine mode
- Added Lambda deployment (default) and ECS deployment (optional)
- Updated region to eu-west-2 (London)
- Added admin endpoints for OCR management
- Created model swapping framework documentation

### Key Changes
| File | Change |
|------|--------|
| `api_server.py` | Added DoclingOCRService, TextractOCRService, OCRServiceFactory |
| `Dockerfile.lambda` | Lambda deployment (Textract, EasyOCR only) |
| `Dockerfile.ecs` | ECS deployment (all 4 engines) |
| `requirements.txt` | Added docling>=2.0.0 |
| `requirements-lambda.txt` | Lambda-optimized (no docling) |
| `DEPLOYMENT_GUIDE.md` | Full deployment documentation |
| `README.md` | Updated with model swapping framework |

### Deployment Modes
| Mode | Engines | Monthly Cost | Default |
|------|---------|--------------|---------|
| Lambda (Default) | Textract, EasyOCR | ~$29 | ✅ |
| ECS (Optional) | All 4 engines | ~$46 | ❌ |

---

## Phase 2: Easy LLM Model Swapping
**Status**: PENDING

### Goal
Make Bedrock model selection configurable at runtime via API request (same pattern as OCR swapping).

### Tasks
- [ ] Add `llm_model` field to harvest endpoint request
- [ ] Support multiple Bedrock models:
  - [ ] Claude (Anthropic) - `anthropic.claude-sonnet-4-20250507`
  - [ ] Llama (Meta) - `meta.llama3-2-90b-instruct-v1:0`
  - [ ] Titan (Amazon) - `amazon.titan-text-premier-v1:0`
- [ ] Update BedrockClient to accept model_id parameter
- [ ] Add available models to /models endpoint
- [ ] Document LLM model selection

### Example Request (After Implementation)
```json
{
  "document": "<base64>",
  "question": "Summarize this document",
  "llm_model": "anthropic.claude-sonnet-4-20250507",
  "prompt": "You are a financial analyst..."
}
```

### Notes
- Follow same pattern as OCR model swapping
- Keep default model as Claude Sonnet
- Validate model IDs against Bedrock available models

---

## Phase 3: OCR Benchmark System
**Status**: PENDING

### Goal
Create automated benchmark system using SynthFactory for ground truth generation to evaluate OCR engine performance.

### Tasks
- [ ] Create benchmark suite (`tests/benchmarks/`)
- [ ] Integrate SynthFactory for ground truth document generation
- [ ] Implement benchmark runner:
  - [ ] Run all 4 OCR engines on same document
  - [ ] Compare against SynthFactory ground truth
  - [ ] Measure: accuracy, confidence, processing time, cost
- [ ] Generate benchmark reports
- [ ] Track performance over time

### Benchmark Evaluation
| Document Type | Best Engine | Notes |
|---------------|-------------|-------|
| Invoices | TBD | Testing required |
| Receipts | TBD | Testing required |
| Bank Statements | TBD | Testing required |
| Contracts | TBD | Testing required |

### Notes
- Use SynthFactory for controlled ground truth generation
- Focus on financial document types (client focus)
- Document performance characteristics per engine

---

## Phase 4: Committee Mode (Smart Routing)
**Status**: PENDING

### Goal
Optimize OCR engine selection by running a sample through all engines and selecting the best one for the full document.

### Concept
```
Full Document Upload
        ↓
Sample Extraction (first page)
        ↓
All 4 Engines Process Sample
        ↓
Select Best Engine Based on Sample Performance
        ↓
Selected Engine Processes Full Document
        ↓
Result (with metadata about engine selection)
```

### Tasks
- [ ] Implement sample extraction (first page or random)
- [ ] Add sample processing endpoint
- [ ] Create engine selection algorithm based on sample performance
- [ ] Add committee mode toggle to API
- [ ] Include selection metadata in response
- [ ] Add caching for repeat documents

### Benefits
- Cost efficient (4 engines × sample vs 4 engines × full)
- Adaptive (different engines for different documents)
- Fast selection (sample processing is quick)
- Transparent (includes selection metadata)

### Configuration Options
| Option | Description |
|--------|-------------|
| `committee_mode` | Enable/disable smart routing |
| `sample_size` | Number of pages to sample |
| `sample_strategy` | "first_page", "random", "complex_page" |
| `fallback_engine` | Engine to use if sample fails |

### Notes
- Start with first page sampling as default
- Consider caching sample results for repeat documents
- Allow opt-out for callers who want to force specific engine

---

## Future Enhancements (Backlog)
**Status**: IDEAS

### Potential Features
- **Auto-Selection Based on Document Type**: Learn which engine is best for different document types
- **Cost Budgeting**: Set monthly cost limits, auto-select cheaper engines when approaching budget
- **Ensemble Mode**: Combine results from multiple engines for higher accuracy
- **Custom Evaluation Metrics**: Allow clients to define their own success criteria
- **Multi-Language Support**: Evaluate engine performance per language

---

## Quick Reference

### Current Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/admin/ocr/status` | OCR engine status |
| POST | `/admin/ocr/unload` | Unload current engine |
| POST | `/extract/text` | Extract plain text from document |
| POST | `/extract/bbox` | Extract text with bounding boxes |
| POST | `/harvest` | Extract text + Bedrock Q&A |
| GET | `/models` | List available models |

### Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SHOESHINE_API_KEY` | Yes | - | API key for authentication |
| `AWS_REGION` | No | `eu-west-2` | AWS region |
| `BEDROCK_MODEL_ID` | Yes | - | Bedrock model |
| `SHOESHINE_DEFAULT_OCR_ENGINE` | No | `auto` | Default OCR engine |
| `SHOESHINE_DEPLOY_MODE` | No | `lambda` | Deployment mode (lambda/ecs) |
| `SHOESHINE_OCR_IDLE_TIMEOUT` | No | `600` | Idle timeout in seconds |
| `SHOESHINE_ADMIN_API_KEY` | No | - | Admin API key |
| `ALLOWED_S3_BUCKETS` | No | `` | Comma-separated S3 buckets |

### Deploy via Bamboo
```bash
# Configure in Bamboo:
# - AWS credentials
# - Terraform variables
# - S3 backend for state
```

---

## Deployment Roadmap

### Phase 1: Initial Deployment (COMPLETED ✓)
- [x] Lambda deployment with Textract + EasyOCR
- [x] Per-request OCR engine selection
- [x] Admin endpoints for OCR management
- [x] Documentation

### Phase 2: LLM Model Swapping (NEXT)
- [ ] Add per-request LLM model selection
- [ ] Update harvest endpoint
- [ ] Test with multiple Bedrock models
- [ ] Document LLM selection

### Phase 3: Benchmark System (FUTURE)
- [ ] Integrate SynthFactory for ground truth
- [ ] Create benchmark suite
- [ ] Evaluate all 4 OCR engines
- [ ] Generate performance reports

### Phase 4: Committee Mode (FUTURE)
- [ ] Implement sample extraction
- [ ] Create smart routing logic
- [ ] Add committee mode toggle
- [ ] Optimize for cost/quality balance

---

## Plan Changes Log

| Date | Change | Reason |
|------|--------|--------|
| Jan 15, 2026 | Added Phase 3 (Benchmark System) | Future enhancement using SynthFactory |
| Jan 15, 2026 | Added Phase 4 (Committee Mode) | Cost optimization for production |
| Jan 15, 2026 | Changed region to eu-west-2 | Client requirement (London) |
| Jan 15, 2026 | Split deployment into Lambda (default) and ECS (optional) | Cost optimization |

---

## Next Session Checklist

- [ ] Review current branch status: `git status`
- [ ] Test locally (optional):
  ```bash
  export AWS_REGION=eu-west-2
  export AWS_ACCESS_KEY_ID=xxx
  export AWS_SECRET_ACCESS_KEY=xxx
  docker-compose up --build
  ```
- [ ] Deploy Phase 1 via Bamboo if ready
- [ ] Validate Phase 1 in production (1-2 weeks)
- [ ] Pick up Phase 2 (LLM model swapping)

---

## Notes
- Branch: `feature/ocr-model-swapping` (from `aws-bedrock-only`)
- Main deployment: Bamboo (Bitbucket)
- Terraform state: S3 backend (configure in Bamboo)
- No local LLM required (Bedrock only)
- Default deployment: Lambda with Textract + EasyOCR (cost-effective)
- Optional deployment: ECS with all 4 engines (when needed)
