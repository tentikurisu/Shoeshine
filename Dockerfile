# Shoeshine API Server - Dockerfile
# A lightweight document scanning service with FastAPI and local LLM support

FROM python:3.13-slim

LABEL maintainer="shoeshine"
LABEL description="Document scanning service for local LLMs using OCR"
LABEL version="1.0.0"

# Install system dependencies for OpenCV and PaddleOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements-api.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy application code
COPY src/ /app/src/
COPY requirements.txt .
COPY config.yaml .

# Create directories
RUN mkdir -p /app/data/raw /app/data/index /app/data/out

# Environment variables
ENV SHOESHINE_HOST=0.0.0.0
ENV SHOESHINE_PORT=8000
ENV SHOESHINE_ENV=local
ENV SHOESHINE_REQUIRE_API_KEY=false
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI server with uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
