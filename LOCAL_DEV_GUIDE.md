# Shoeshine Local-Only Development Guide

## Overview

This branch (`local-only`) is a **dedicated local development environment** for Shoeshine, focusing on:

- **Local LLM Integration**: Ollama, vLLM, LM Studio
- **Full OCR Support**: EasyOCR, Docling, Tesseract
- **Hardware Optimization**: Efficient resource usage
- **Benchmarking**: SynthFactory integration for ground truth testing

---

## Branch Structure

```
main (springboard)
    └── local-only (this branch)
        ├── feature/ocr-swapping       # OCR engine selection
        ├── feature/llm-detection       # LLM platform auto-detection
        ├── feature/benchmarking        # Performance evaluation
        └── feature/committee-mode      # Smart routing (future)
```

---

## Development Roadmap

### Phase 1: OCR Engine Swapping ✅ (Complete)
- [x] EasyOCR integration
- [x] Docling integration
- [x] Tesseract integration
- [x] Per-request engine selection via `?ocr_engine=` parameter

### Phase 2: LLM Platform Detection ✅ (Complete)
- [x] Ollama auto-detection
- [x] vLLM auto-detection
- [x] LM Studio auto-detection
- [x] `/admin/platforms` endpoint
- [x] `/admin/status` endpoint

### Phase 2.5: Hardware Detection & Monitoring ✅ (Complete)
- [x] Automatic hardware detection (CPU, RAM, GPU)
- [x] Resource monitoring (CPU, memory, GPU usage)
- [x] LLM framework detection (Ollama, vLLM, LM Studio)
- [x] Performance recommendations based on hardware
- [x] `/admin/hardware` endpoint
- [x] `/admin/resources` endpoint
- [x] `/admin/diagnostics` endpoint
- [x] All-in-one CLI tool (`shoesine.py`)

### Phase 3: Benchmarking (Future)
- [ ] SynthFactory integration
- [ ] Ground truth generation
- [ ] Accuracy comparison
- [ ] Performance reports

### Phase 4: Committee Mode (Future)
- [ ] Sample-based smart routing
- [ ] Cost optimization
- [ ] Auto-engine selection

---

## Quick Start

### Docker Compose (Recommended)
```bash
git checkout local-only
docker compose up --build -d
```

### Direct Python
```bash
git checkout local-only
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama serve
ollama pull llama3
python api_server.py
```

### Using the CLI Tool
```bash
# Run system diagnostics
python shoeshine.py diag

# Check dependencies and services
python shoeshine.py check

# Start the API server
python shoeshine.py run

# Start Ollama
python shoeshine.py start-ollama

# Pull a model
python shoeshine.py pull llama3

# Run tests
python shoeshine.py test

# Monitor resources
python shoeshine.py monitor
```

---

## API Usage

### OCR Engine Selection
```bash
# Use default (easyocr)
curl -X POST "http://localhost:8000/extract/text" \
  -F "document=@doc.pdf"

# Force specific engine
curl -X POST "http://localhost:8000/extract/text?ocr_engine=docling" \
  -F "document=@doc.pdf"

curl -X POST "http://localhost:8000/extract/text?ocr_engine=tesseract" \
  -F "document=@doc.pdf"
```

### LLM Platform Detection
```bash
# Check detected platforms
curl http://localhost:8000/admin/platforms

# Harvest with default LLM
curl -X POST "http://localhost:8000/harvest" \
  -F "document=@doc.pdf" \
  -F "fields=account_number,total_amount"

# Force specific model
curl -X POST "http://localhost:8000/harvest" \
  -F "document=@doc.pdf" \
  -F "fields=account_number,total_amount" \
  -F "llm_model=llama3"
```

### Hardware Detection & Monitoring
```bash
# Get hardware information (CPU, RAM, GPU)
curl http://localhost:8000/admin/hardware

# Get current resource usage (CPU, memory, GPU)
curl http://localhost:8000/admin/resources

# Run complete system diagnostics
curl http://localhost:8000/admin/diagnostics
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOESHINE_OLLAMA_URL` | http://localhost:11434 | Ollama URL |
| `SHOESHINE_LLM_MODEL` | llama3 | Default LLM |
| `SHOESHINE_DEFAULT_OCR_ENGINE` | easyocr | Default OCR |
| `SHOESHINE_OCR_IDLE_TIMEOUT` | 600 | Idle timeout (sec) |
| `SHOESHINE_ADMIN_API_KEY` | - | Admin API key |

---

## Hardware Considerations

### Minimum Requirements
- CPU: 2 cores
- RAM: 4GB
- Storage: 2GB

### Recommended (with GPU)
- GPU: NVIDIA 4GB+ VRAM
- RAM: 8GB+
- CUDA: 11.8 or 12.x

### Resource Limits (Docker)
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
```

---

## Project Structure

```
local-only/
├── api_server.py           # Main API with OCR/LLM services
├── docker-compose.yml      # Full stack (Shoeshine + Ollama + WebUI)
├── requirements.txt        # Python dependencies
├── DEPLOYMENT_LOCAL.md     # Deployment guide
├── .env.example            # Environment template
├── README.md               # Main documentation
└── data/                   # Test documents
```

---

## Key Differences from AWS Branch

| Feature | AWS-Only | Local-Only |
|---------|----------|------------|
| **LLM** | Bedrock | Ollama, vLLM, LM Studio |
| **OCR** | Textract, EasyOCR | All 4 engines |
| **Deployment** | Lambda/ECS | Docker, Python, Systemd |
| **Cost** | Pay-per-request | Hardware only |
| **Cold Starts** | ~5-10s | None |

---

## Testing

### Health Check
```bash
curl http://localhost:8000/health
```

### LLM Platforms
```bash
curl http://localhost:8000/admin/platforms
```

### OCR Benchmark
```bash
# Test all OCR engines
for engine in easyocr docling tesseract; do
  echo "Testing $engine..."
  curl -X POST "http://localhost:8000/extract/text?ocr_engine=$engine" \
    -F "document=@data/raw/doc_00000_9795.jpg" \
    | jq -r '.processing_time_ms'
done
```

---

## Troubleshooting

### Ollama Not Detected
```bash
# Check if running
curl http://localhost:11434/api/version

# Restart Ollama
ollama serve

# Pull model
ollama pull llama3
```

### OCR Not Available
```bash
# Check Tesseract
tesseract --version

# Install Tesseract (Ubuntu)
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

### Out of Memory
```bash
# Check memory
free -h

# Clear Docker cache
docker system prune -a
```

---

## Next Steps

1. **Test the branch** - Verify all features work
2. **Implement benchmarking** - Phase 3 (SynthFactory)
3. **Add committee mode** - Phase 4

---

## References

- [DEPLOYMENT_LOCAL.md](DEPLOYMENT_LOCAL.md) - Full deployment guide
- [README.md](README.md) - Main documentation
- [docker-compose.yml](docker-compose.yml) - Stack configuration
- `.env.example` - Environment template
