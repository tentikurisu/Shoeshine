# Shoeshine - Document Scanning Layer for Local LLMs

**A document-to-text translation layer using deep learning OCR with image preprocessing.**

---

## What is Shoeshine?

Shoeshine extracts text from images and PDFs using OCR, then feeds the extracted text to local LLMs (Ollama, LM Studio) or cloud models (AWS Bedrock). It is **not an LLM itself** - it is a tool that converts documents to text.

### Key Features

| Feature | Description |
|--------|-------------|
| **Deep Learning OCR** | EasyOCR (CNN-based) with image preprocessing pipeline for high accuracy |
| **Multiple Engines** | EasyOCR (default, high accuracy), Tesseract (fast fallback), PaddleOCR (available, not integrated) |
| **Local Processing** | OCR runs locally - your data never leaves your infrastructure |
| **Model-agnostic** | Works with any LLM - Ollama, Bedrock, LM Studio, vLLM |
| **Structured Extraction** | Optional LLM integration for key-value extraction (harvest endpoint) |
| **Zero Retention** | Documents processed in memory, never stored or cached |

---

## Shoeshine vs. AI Systems

| Aspect | Shoeshine | AI Systems (LLMs) |
|--------|-----------|-------------------|
| **Technology** | Deep learning OCR (EasyOCR) | Transformer-based LLMs |
| **What it does** | Extracts text from images | Generates and reasons about text |
| **Training** | No training on your data | May train on public data |
| **Retention** | Zero - processed in memory | Depends on implementation |
| **Use case** | Document → text | Text → answer/analysis |

Shoeshine is a **tool for text extraction**. The optional `harvest` endpoint feeds extracted text to LLMs (Ollama, Bedrock) for structured extraction, but Shoeshine itself is not an LLM and doesn't generate responses.

---

## How OCR Works

Shoeshine uses a two-stage pipeline for high-accuracy text extraction:

### Stage 1: Image Preprocessing

Before OCR runs, images are enhanced to maximize accuracy:

| Step | Operation | Purpose |
|------|-----------|---------|
| 1 | Upscale to ≥1400px | More pixels = more detail for the model |
| 2 | Grayscale conversion | Removes color noise, focuses on shapes |
| 3 | Median blur (k=3) | Removes speckle noise from scanning |
| 4 | CLAHE (clip=2.0, 8x8) | Adaptive contrast - makes faint text visible |
| 5 | Otsu thresholding | Optimal black/white separation |
| 6 | Morphological opening | Removes paper grain and small artifacts |

### Stage 2: Deep Learning OCR

- **Engine**: EasyOCR (CNN-based neural network)
- **Model**: ~300MB, downloaded on first run
- **Languages**: English (configurable)
- **Output**: Text + confidence scores + bounding boxes

**Why preprocessing matters**: EasyOCR is already highly accurate due to its deep learning models. The preprocessing pipeline ensures the input image is clean and high-contrast, which significantly improves OCR accuracy on real-world documents with scanning artifacts, faded ink, or poor lighting.

---

## OCR Engines

### EasyOCR (Default)

- **Type**: CNN-based deep learning
- **Accuracy**: High (neural network models)
- **Size**: ~300MB (downloaded on first run)
- **Dependencies**: Pure Python, no system install required
- **Speed**: Slower than Tesseract, higher accuracy

### Tesseract (Fallback)

- **Type**: Traditional OCR (LSTM-based)
- **Accuracy**: Medium (legacy technology)
- **Size**: Lightweight (~20MB)
- **Dependencies**: Requires system installation
- **Speed**: Fast, good for simple documents

### PaddleOCR (Available)

- **Type**: Deep learning OCR (PP-OCRv2/v3)
- **Accuracy**: High
- **Status**: Available in codebase, not currently integrated in API
- **Note**: Can be enabled via configuration if needed

**Why EasyOCR by default?**
Deep learning models significantly outperform traditional OCR on complex documents, faded text, varied fonts, and poor scan quality.

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/shoeshine.git
cd shoeshine

# Start the service
docker compose up --build

# In another terminal, test it
curl http://localhost:8000/health

# Or visit interactive documentation
# http://localhost:8000/docs - Swagger UI
# http://localhost:8000/redoc - ReDoc

# Extract text from a document
curl -X POST http://localhost:8000/extract/text \
  -F "document=@path/to/your-document.jpg"

# Or with bounding boxes
curl -X POST http://localhost:8000/extract/bbox \
  -F "document=@path/to/your-receipt.png"
```

> **Note:** Sample documents are available in `data/raw/` for testing. Use `data/raw/doc_00000_9795.jpg` as an example.

### Option 2: Local Development

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate
.venv\Scripts\pip install -r requirements.txt

# Start server
python api_server.py

# Visit interactive documentation
# http://localhost:8000/docs - Swagger UI
# http://localhost:8000/redoc - ReDoc

# Or with debug mode
python api_server.py --host 0.0.0.0 --port 8000
```

### Option 3: Production with Docker

```bash
# With API key authentication
docker compose up -d

# With custom Ollama URL
SHOESHINE_OLLAMA_URL=http://host.docker.internal:11434 docker compose up -d
```

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check and service status |
| GET | `/models` | List available models and OCR engines |
| POST | `/extract/text` | Extract plain text from documents |
| POST | `/extract/bbox` | Extract text with bounding box coordinates |
| POST | `/harvest` | Structured key-value extraction (requires LLM) |

### Authentication

All endpoints accept an optional `X-API-Key` header for authentication. Configure via the `SHOESHINE_API_KEY` environment variable.

### Interactive API Documentation

Shoeshine includes automatic interactive documentation powered by FastAPI:

- **Swagger UI**: http://localhost:8000/docs
  - Interactive web interface to try all API endpoints
  - View request/response schemas
  - Execute requests directly from your browser

- **ReDoc**: http://localhost:8000/redoc
  - Clean, developer-friendly API documentation
  - Readable API reference

### Example Requests

**Health Check**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-04T00:00:00Z",
  "version": "1.0.0",
  "services": {
    "ocr": true,
    "ollama": false,
    "bedrock": false
  },
  "ocr_engine": "easyocr"
}
```

**Extract Text**
```bash
curl -X POST http://localhost:8000/extract/text \
  -H "X-API-Key: sk-shoeshine-xxxxx" \
  -F "document=@data/raw/doc_00000_9795.jpg"
```

**Response:**
```json
{
  "success": true,
  "id": "shoe-abc12345",
  "object": "text_extraction",
  "text": "Bank Name: Cedar Bank\nAccount: 12345678",
  "processing_time_ms": 1250,
  "model": "shoeshine-ocr"
}
```

**Extract with Bounding Boxes**
```bash
curl -X POST http://localhost:8000/extract/bbox \
  -F "document=@data/raw/doc_00000_9795.jpg" \
  -H "X-API-Key: sk-shoeshine-xxxxx"
```

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "text": "Invoice #12345",
      "confidence": 0.999,
      "bbox": [100, 50, 300, 80]
    }
  ]
}
```

---

## Integration Examples

### Using Ollama

```python
import requests

# Extract text from document
with open("data/raw/doc_00000_9795.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/extract/text",
        files={"document": f}
    )
text = response.json()["text"]

# Send to Ollama
response = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "llama3",
        "messages": [
            {
                "role": "system",
                "content": "Answer based on the provided document text."
            },
            {
                "role": "user",
                "content": f"Document:\n{text}\n\nQuestion: What is the account number?"
            }
        ]
    }
    )
print(response.json()["message"]["content"])
```

**Prerequisites before running example:**
```bash
# 1. Start Shoeshine API server
python api_server.py

# 2. Start Ollama (if not already running)
ollama serve

# 3. Pull the model (if not already downloaded)
ollama pull llama3
```

**Run example:**
```bash
# First, use sample document from repository
python examples/ollama_integration.py data/raw/doc_00000_9795.jpg "What is the account number?"
```

### Using AWS Bedrock

```python
import requests

# Extract text using sample document
with open("data/raw/doc_00000_9795.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/extract/text",
        files={"document": f}
    )
text = response.json()["text"]

# Send to Bedrock
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

response = bedrock.converse(
    modelId="anthropic.claude-sonnet-4-20250507",
    messages=[
        {
            "role": "user",
            "content": [
                {"text": f"Document:\n{text}\n\nQuestion: What is the bank name?"}
            ]
        }
    ],
    inferenceConfig={"maxTokens": 4096, "temperature": 0.0}
)

print(response["output"]["message"]["content"][0]["text"])
```

**Prerequisites before running example:**
```bash
# Start Shoeshine API server
python api_server.py

# Ensure AWS credentials are configured
aws configure
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOESHINE_HOST` | `0.0.0.0` | Host to bind |
| `SHOESHINE_PORT` | `8000` | Port to listen |
| `SHOESHINE_API_KEY` | - | API key for authentication (optional) |
| `SHOESHINE_OLLAMA_URL` | - | Ollama URL for harvest endpoint (optional) |
| `SHOESHINE_LLM_MODEL` | `llama3` | LLM model for harvest |
| `SHOESHINE_OCR_ENGINE` | `easyocr` | OCR engine: `easyocr` (default, high accuracy) or `tesseract` (fast fallback) |
| `AWS_REGION` | - | AWS region for Bedrock (optional) |
| `AWS_ACCESS_KEY_ID` | - | AWS access key ID (optional) |
| `AWS_SECRET_ACCESS_KEY` | - | AWS secret access key (optional) |
| `BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-4-20250507` | Bedrock model ID |

**Engine Selection Guide:**
- Use `easyocr` (default) for best accuracy on complex documents
- Use `tesseract` for speed on simple, clean documents

---

## Architecture

```
┌──────────────────────────────────────────┐
│                    Client Application     │
│         (Your app, routing project)    │
└───────────────────────────────────────┘
                    ↓              Extracts Text → Any Model
└───────────────────────────────────────┘
                  Shoeshine API Server
                  - FastAPI (web framework)
                  - EasyOCR (CNN-based OCR)
                  - Image preprocessing pipeline
                  - Optional: Ollama/Bedrock
                  ↓
                  Zero data retention
```

---

## Deployment

### Local Development

Start with:
```bash
python api_server.py
```

### Docker

```bash
docker compose up --build
```

With environment variables:
```bash
SHOESHINE_API_KEY=sk-your-key docker compose up -d
```

### AWS EC2

```bash
# On EC2 instance
sudo yum install -y docker
sudo systemctl start docker

# Clone and run
git clone https://github.com/your-org/shoeshine.git
cd shoeshine
docker compose up -d
```

### AWS ECS Fargate

1. Push Docker image to ECR:
```bash
aws ecr get-login-password | docker login -u <username> --password-stdin
docker build -t shoeshine-ecs .
docker tag shoeshine-ecs <your-ecr-uri>/shoeshine:latest
docker push <your-ecr-uri>/shoeshine:latest
```

2. Create ECS service (via console or IaC)

### AWS Lambda

1. Build Lambda image:
```bash
docker buildx build --platform linux/amd64 -t shoeshine-lambda .
docker tag shoeshine-lambda <your-ecr-uri>/shoeshine:latest
docker push <your-ecr-uri>/shoeshine-lambda:latest
```

2. Configure Lambda (see [docker-deploy.yml](.github/workflows/docker-deploy.yml))

3. Set up API Gateway

---

## Project Structure

```
shoeshine/
├── api_server.py              # Main API server
├── shoeshine_lib.py           # Core OCR library (legacy, kept for compatibility)
├── ingest.py                 # Batch ingestion tool
├── ask.py                    # Q&A CLI tool
├── config.yaml               # Configuration
├── requirements.txt           # Python dependencies
├── Dockerfile                # Docker container
├── docker-compose.yml          # Docker orchestration
├── tests/                    # Test suite
├── examples/                 # Integration examples
│   ├── ollama_integration.py  # Ollama integration
│   ├── bedrock_integration.py # AWS Bedrock integration
│   └── basic_usage.py          # Basic usage example
├── .gitignore               # Git ignore rules
├── LICENSE                  # MIT License
├── README.md               # This file
└── .github/                 # GitHub workflows
    └── workflows/
        ├── ci.yml          # CI/CD pipeline
        └── docker-deploy.yml  # Docker deployment
```

---

## Privacy & Security

See [PRIVACY.md](PRIVACY.md) for detailed privacy guarantees and security measures.

### Key Points

- **No Data Retention**: Documents are processed in memory only
- **No Training Data**: Extracted text never trains any model
- **Zero External Calls**: OCR runs locally by default
- **Optional Authentication**: API key or IAM-based auth
- **Input Validation**: File type verification, size limits
- **Audit Logging**: Only metadata is logged, not document contents

---

## Troubleshooting

### Connection Refused Error

**Error:** `Connection refused` or `No connection could be made because target machine actively refused it`

**Solution:** Start the Shoeshine API server first:
```bash
# Terminal 1: Start Shoeshine server
python api_server.py

# Terminal 2: Run your examples
python examples/ollama_integration.py data/raw/doc_00000_9795.jpg "What is the account number?"
```

### OCR Initialization Failed

**Error:** `EasyOCR initialization failed` or `OCR not available`

**Solutions:**
1. EasyOCR downloads models on first run (~300MB). Ensure you have internet connection.
2. Check that you have enough disk space.
3. If using Tesseract, install it system-wide:
   - Windows: [Download from UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
   - macOS: `brew install tesseract`
   - Linux: `sudo apt-get install tesseract-ocr`

### Ollama Connection Failed

**Error:** `Failed to connect to Ollama` or harvest endpoint returns 503

**Solutions:**
1. Start Ollama: `ollama serve`
2. Check Ollama is running: `curl http://localhost:11434/api/tags`
3. Pull required model: `ollama pull llama3`
4. Set environment variable if using custom URL: `export SHOESHINE_OLLAMA_URL=http://your-url:11434`

### AWS Bedrock Errors

**Error:** `AccessDenied` or `ValidationException`

**Solutions:**
1. Configure AWS credentials: `aws configure`
2. Ensure your AWS account has Bedrock access enabled in the region
3. Verify the model ID is available in your region (e.g., `anthropic.claude-sonnet-4-20250507`)
4. Check IAM permissions include `bedrock:InvokeModel`

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests for new features
5. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) file.

---

## Changelog

### v1.0.0 - Initial Release

**Features**
- EasyOCR integration with automatic model download
- Tesseract fallback support
- OpenAI-compatible API responses
- Structured extraction with Ollama/Bedrock integration
- AWS Bedrock support for Lambda deployment
- Docker support with multi-arch builds
- Comprehensive test suite with pytest
- GitHub Actions CI/CD workflows
- Docker deployment for ECS, Lambda, EC2

**Bug Fixes**
- Fixed PaddleOCR 3.x API compatibility issues
- Switched to EasyOCR for better cross-platform support
- Fixed async file upload handling in API endpoints
- Added proper error handling and logging
- Added multiple OCR engines with fallback support

---

## Acknowledgments

- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - OCR engine
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [OpenCV](https://opencv.org/) - Image processing
- [Ollama](https://ollama.com/) - Local LLM (integration option)
- [AWS Bedrock](https://aws.amazon.com/bedrock/) - AI model (integration option)
