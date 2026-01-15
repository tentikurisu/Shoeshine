# Shoeshine Local-Only Deployment Guide

## Deployment Options

| Method | Best For | GPU Support | Difficulty |
|--------|----------|-------------|------------|
| **Docker Compose** | Development, testing | Via Docker | Easy |
| **Direct Python** | Simple deployments | Native | Easy |
| **Systemd Service** | Production-like local | Native | Medium |
| **Kubernetes** | Large-scale local | Via node pools | Hard |

---

## Option 1: Docker Compose (Recommended for Dev)

### Quick Start
```bash
# Clone and start
git clone <repo>
cd shoeshine
git checkout local-only
docker compose up --build -d

# Check logs
docker compose logs -f

# Stop
docker compose down
```

### With GPU Support
```yaml
# Add to shoeshine service in docker-compose.yml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

### Access
- API: http://localhost:8000
- Ollama: http://localhost:11434
- API Docs: http://localhost:8000/docs

---

## Option 2: Direct Python (Simplest)

### Prerequisites
```bash
# Install Python 3.11+
python --version

# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
```

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Ollama (separate terminal)
ollama serve
ollama pull llama3

# Start Shoeshine
python api_server.py
```

### Access
- API: http://localhost:8000

---

## Option 3: Systemd Service (Production-Like)

### Create Service File
```bash
sudo nano /etc/systemd/system/shoeshine.service
```

```ini
[Unit]
Description=Shoeshine Document OCR API
After=network.target ollama.service

[Service]
Type=simple
User=shoeshine
WorkingDirectory=/opt/shoeshine
ExecStart=/opt/shoeshine/venv/bin/python api_server.py
Restart=always
RestartSec=10
Environment=SHOESHINE_HOST=0.0.0.0
Environment=SHOESHINE_PORT=8000
Environment=SHOESHINE_OLLAMA_URL=http://localhost:11434
Environment=SHOESHINE_LLM_MODEL=llama3
Environment=SHOESHINE_ENV=production

[Install]
WantedBy=multi-user.target
```

### Install
```bash
# Create user
sudo useradd -r -s /bin/false shoeshine

# Create directory
sudo mkdir -p /opt/shoeshine
sudo chown shoeshine:shoeshine /opt/shoeshine

# Copy files
sudo cp -r . /opt/shoeshine/
sudo chmod +x /opt/shoeshine/venv/bin/python

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable shoeshine
sudo systemctl start shoeshine

# Check status
sudo systemctl status shoeshine

# View logs
sudo journalctl -u shoeshine -f
```

---

## Hardware Considerations

### Minimum Requirements
- CPU: 2 cores
- RAM: 4GB (8GB recommended)
- Storage: 2GB for models

### With GPU (Recommended)
- GPU: NVIDIA with 4GB+ VRAM
- CUDA: 11.8+ or 12.x
- Drivers: 535+

### Resource Allocation

#### Docker Compose (Limit Resources)
```yaml
services:
  shoeshine:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

#### Systemd (Limit Resources)
```ini
[Service]
MemoryMax=4G
MemoryHigh=3G
CPUQuota=200%
```

---

## Ollama Configuration

### Pull Models
```bash
# Lightweight model (fast)
ollama pull llama3.2:3b

# Standard model
ollama pull llama3

# Large model (more RAM/GPU needed)
ollama pull llama3:70b
```

### GPU Memory
```bash
# Check GPU memory usage
nvidia-smi

# Set Ollama GPU layers
export CUDA_VISIBLE_DEVICES=0
export OLLAMA_GPU_LAYERS=35
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOESHINE_HOST` | 0.0.0.0 | Host to bind |
| `SHOESHINE_PORT` | 8000 | Port to listen |
| `SHOESHINE_OLLAMA_URL` | http://localhost:11434 | Ollama URL |
| `SHOESHINE_LLM_MODEL` | llama3 | Default LLM model |
| `SHOESHINE_DEFAULT_OCR_ENGINE` | easyocr | Default OCR engine |
| `SHOESHINE_OCR_IDLE_TIMEOUT` | 600 | Idle timeout (seconds) |
| `SHOESHINE_API_KEY` | - | API key (optional) |
| `SHOESHINE_ADMIN_API_KEY` | - | Admin API key |
| `SHOESHINE_ENV` | local | Environment (local/production) |

### Example .env File
```bash
# Create .env file
cat > .env << EOF
SHOESHINE_HOST=0.0.0.0
SHOESHINE_PORT=8000
SHOESHINE_OLLAMA_URL=http://localhost:11434
SHOESHINE_LLM_MODEL=llama3
SHOESHINE_DEFAULT_OCR_ENGINE=easyocr
SHOESHINE_ENV=production
# SHOESHINE_API_KEY=your-secret-key
EOF
```

---

## Health Checks

### Docker Compose
```bash
# Check service health
docker compose ps

# API health
curl http://localhost:8000/health

# LLM platforms
curl http://localhost:8000/admin/platforms
```

### Systemd
```bash
# Service status
sudo systemctl status shoeshine

# API health
curl http://localhost:8000/health

# View logs
sudo journalctl -u shoeshine -n 50
```

---

## Troubleshooting

### OCR Not Available
```bash
# Check Tesseract
tesseract --version

# Reinstall Tesseract (Ubuntu)
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

### Ollama Not Detected
```bash
# Check if Ollama is running
curl http://localhost:11434/api/version

# Restart Ollama
sudo systemctl restart ollama

# Check logs
sudo journalctl -u ollama -f
```

### Out of Memory
```bash
# Check memory usage
free -h

# Check disk space
df -h

# Clear Docker cache
docker system prune -a
```

---

## Production Recommendations

1. **Use systemd service** for reliability
2. **Set API keys** for security
3. **Limit resources** to prevent system overload
4. **Monitor logs** regularly
5. **Set up backups** of Ollama models
6. **Use GPU** if available for faster OCR/LLM
7. **Set OLLAMA_KEEP_ALIVE** to prevent model unloading

---

## Quick Reference

```bash
# Development (Docker Compose)
docker compose up --build -d
docker compose logs -f
docker compose down

# Production (Systemd)
sudo systemctl start shoeshine
sudo systemctl stop shoeshine
sudo systemctl restart shoeshine
sudo journalctl -u shoeshine -f

# API
curl http://localhost:8000/health
curl http://localhost:8000/docs
```
