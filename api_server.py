"""
Shoeshine API Server - Document Scanning Layer for Local LLMs

A lightweight, model-agnostic document scanning service that translates
images/PDFs to structured text for consumption by local LLMs.

Philosophy:
    This is NOT AI. It's a document-to-text translator using OCR techniques.
    No training, no retention, no embeddings stored. Pure extraction.

Usage:
    python api_server.py
    docker compose up --build

Environment Variables:
    SHOESHINE_API_KEY           - API key for authentication (optional)
    SHOESHINE_HOST              - Host to bind (default: 0.0.0.0)
    SHOESHINE_PORT              - Port to listen (default: 8000)
    SHOESHINE_OLLAMA_URL        - Ollama URL (default: http://localhost:11434)
    SHOESHINE_LLM_MODEL         - LLM model name (default: llama3)
    SHOESHINE_DEFAULT_OCR_ENGINE - OCR engine: easyocr (default), docling, tesseract
    SHOESHINE_OCR_IDLE_TIMEOUT  - Idle timeout in seconds (default: 600)
    SHOESHINE_ADMIN_API_KEY     - Admin API key for management endpoints

OCR Engines (Local):
    - EasyOCR: Default, pure Python (~300MB models on first run)
    - Tesseract: Requires system installation
    - Docling: Full document parsing, best for PDFs
"""

import os
import time
import uuid
import io
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import cv2
import numpy as np
import requests
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel, Field


# ============================================================================
# Pydantic Models (OpenAI-Compatible)
# ============================================================================


class UsageInfo(BaseModel):
    """Token usage information (OpenAI-compatible format)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_text(cls, text: str) -> UsageInfo:
        token_count = len(text) // 4
        return cls(prompt_tokens=token_count, total_tokens=token_count)


class BBoxItem(BaseModel):
    """Bounding box item with text."""

    text: str
    confidence: float
    bbox: List[int]


class ExtractResponse(BaseModel):
    """Response for text extraction (OpenAI-compatible format)."""

    success: bool
    id: str = Field(default_factory=lambda: f"shoe-{uuid.uuid4().hex[:8]}")
    object: str = "text_extraction"
    created: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    text: str
    items: Optional[List[BBoxItem]] = None
    usage: Optional[UsageInfo] = None
    model: str = "shoeshine-ocr"
    processing_time_ms: Optional[int] = None


class HarvestItem(BaseModel):
    """Extracted item for harvest response."""

    key: str
    value: str
    where: Optional[str] = None


class HarvestResponse(BaseModel):
    """Response with extracted key-value pairs."""

    success: bool
    id: str = Field(default_factory=lambda: f"shoe-{uuid.uuid4().hex[:8]}")
    object: str = "text_extraction.harvest"
    created: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    items: List[HarvestItem]
    usage: Optional[UsageInfo] = None
    model: str = "shoeshine-harvest"
    processing_time_ms: Optional[int] = None


class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "shoeshine"


class ModelsResponse(BaseModel):
    """Response listing available models."""

    object: str = "list"
    data: List[ModelInfo]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str = "1.0.0"
    services: Dict[str, bool]
    ocr_engine: str


# ============================================================================
# OCR Service Classes (Inline)
# ============================================================================


@dataclass
class ApiConfig:
    """API configuration from environment variables."""

    api_key: Optional[str]
    host: str
    port: int
    ollama_url: Optional[str]
    llm_model: Optional[str]
    default_ocr_engine: str
    ocr_idle_timeout_seconds: int
    admin_api_key: Optional[str]

    @classmethod
    def from_env(cls) -> ApiConfig:
        return cls(
            api_key=os.getenv("SHOESHINE_API_KEY"),
            host=os.getenv("SHOESHINE_HOST", "0.0.0.0"),
            port=int(os.getenv("SHOESHINE_PORT", "8000")),
            ollama_url=os.getenv("SHOESHINE_OLLAMA_URL"),
            llm_model=os.getenv("SHOESHINE_LLM_MODEL", "llama3"),
            default_ocr_engine=os.getenv("SHOESHINE_DEFAULT_OCR_ENGINE", "easyocr"),
            ocr_idle_timeout_seconds=int(
                os.getenv("SHOESHINE_OCR_IDLE_TIMEOUT", "600")
            ),
            admin_api_key=os.getenv("SHOESHINE_ADMIN_API_KEY"),
        )


class EasyOCRService:
    """OCR service using EasyOCR."""

    def __init__(self):
        try:
            import easyocr

            self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            self.available = True
        except Exception as e:
            print(f"EasyOCR initialization failed: {e}")
            self.reader = None
            self.available = False

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "OCR not available",
                "text": "",
                "items": [],
            }

        try:
            result = self.reader.readtext(img_bgr)

            items = []
            for detection in result:
                bbox, text, confidence = detection
                if text and text.strip():
                    if isinstance(bbox, list) and len(bbox) == 4:
                        xs = [int(p[0]) for p in bbox]
                        ys = [int(p[1]) for p in bbox]
                        bbox_list = [min(xs), min(ys), max(xs), max(ys)]
                    else:
                        bbox_list = [0, 0, 0, 0]

                    items.append(
                        {
                            "text": text.strip(),
                            "confidence": float(confidence),
                            "bbox": bbox_list,
                        }
                    )

            items.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
            text = " ".join(item["text"] for item in items)

            return {"success": True, "text": text, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class TesseractOCRService:
    """OCR service using Tesseract."""

    def __init__(self):
        try:
            import pytesseract
            from pytesseract import Output

            self.pytesseract = pytesseract
            self.Output = Output
            self.available = True
        except Exception as e:
            print(f"Tesseract initialization failed: {e}")
            self.pytesseract = None
            self.available = False

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "Tesseract not available",
                "text": "",
                "items": [],
            }

        try:
            data = self.pytesseract.image_to_data(img_bgr, output_type=self.Output.DICT)

            items = []
            for i, text in enumerate(data["text"]):
                if text and text.strip():
                    conf = int(data["conf"][i]) if data["conf"][i] > -1 else 0
                    x, y, w, h = (
                        data["left"][i],
                        data["top"][i],
                        data["width"][i],
                        data["height"][i],
                    )

                    items.append(
                        {
                            "text": text.strip(),
                            "confidence": conf / 100.0,
                            "bbox": [x, y, x + w, y + h],
                        }
                    )

            items.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
            text = " ".join(item["text"] for item in items)

            return {"success": True, "text": text, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class OCRService:
    """Unified OCR service that tries multiple backends."""

    def __init__(self, engine: str = "easyocr"):
        """Initialize OCR service with specified engine."""
        self.engine = engine
        self.primary = None
        self.fallback = None
        self.available = False

        if engine == "easyocr":
            self.primary = EasyOCRService()
            self.fallback = TesseractOCRService()
        else:
            self.primary = TesseractOCRService()
            self.fallback = EasyOCRService()

        self.available = self.primary.available or self.fallback.available

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image using primary or fallback engine."""
        if self.primary and self.primary.available:
            result = self.primary.process(img_bgr)
            if result["success"]:
                return result

        if self.fallback and self.fallback.available:
            result = self.fallback.process(img_bgr)
            if result["success"]:
                return result

        return {
            "success": False,
            "error": "No OCR engine available",
            "text": "",
            "items": [],
        }


class OllamaService:
    """Service for Ollama integration."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=2)
            return response.status_code == 200
        except:
            return False

    def extract_structured(
        self, text: str, fields: List[str], system_prompt: Optional[str] = None
    ) -> List[Dict]:
        """Extract structured data from text using Ollama."""
        if not self.is_available():
            return []

        from api_server import ApiConfig

        config = ApiConfig.from_env()
        model = config.llm_model or "llama3"

        default_system = """You are extracting structured data from a document.
Extract requested fields as JSON array of objects.
Output format: [{"key": "field_name", "value": "extracted value", "where": "location"}]

If a field is not found, include it with value "NOT_FOUND"."""

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt or default_system},
                        {
                            "role": "user",
                            "content": f"Extract these fields: {', '.join(fields)}\n\nDocument:\n{text}",
                        },
                    ],
                    "stream": False,
                },
                timeout=120,
            )

            if response.status_code != 200:
                return []

            result = response.json()
            content = result.get("message", {}).get("content", "")

            try:
                import json

                data = json.loads(content)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "items" in data:
                    return data["items"]
            except:
                pass

        except Exception as e:
            print(f"Ollama extraction failed: {e}")

        return []


# ============================================================================
# LLM Platform Detection (Ollama, vLLM, LM Studio, etc.)
# ============================================================================


class LLMPlatform:
    """Represents a detected LLM platform."""

    def __init__(self, name: str, url: str, models: List[str]):
        self.name = name
        self.url = url
        self.models = models

    def __repr__(self):
        return f"LLMPlatform({self.name}, {len(self.models)} models)"


def detect_llm_platforms() -> List[LLMPlatform]:
    """
    Detect available LLM platforms on the system.

    Checks for:
    - Ollama (ports 11434, 127.0.0.1:11434)
    - vLLM (ports 8000, 127.0.0.1:8000)
    - LM Studio (ports 1234, 127.0.0.1:1234)
    """
    platforms = []
    httpx = __import__("httpx")

    # Ollama detection
    ollama_urls = [
        os.getenv("SHOESHINE_OLLAMA_URL", "http://localhost:11434"),
        "http://localhost:11434",
        "http://127.0.0.1:11434",
    ]

    for url in ollama_urls:
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{url}/api/tags")
                if response.status_code == 200:
                    models = [m["name"] for m in response.json().get("models", [])]
                    if models:
                        platforms.append(LLMPlatform("ollama", url, models))
                        print(f"  Ollama detected: {len(models)} models at {url}")
                        break
        except Exception:
            continue

    # vLLM detection
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get("http://localhost:8000/v1/models")
            if response.status_code == 200:
                data = response.json()
                models = [m["id"] for m in data.get("data", [])]
                if models:
                    platforms.append(
                        LLMPlatform("vllm", "http://localhost:8000", models)
                    )
                    print(
                        f"  vLLM detected: {len(models)} models at http://localhost:8000"
                    )
    except Exception:
        pass

    # LM Studio detection
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get("http://localhost:1234/v1/models")
            if response.status_code == 200:
                data = response.json()
                models = [m["id"] for m in data.get("data", [])]
                if models:
                    platforms.append(
                        LLMPlatform("lmstudio", "http://localhost:1234", models)
                    )
                    print(
                        f"  LM Studio detected: {len(models)} models at http://localhost:1234"
                    )
    except Exception:
        pass

    return platforms


def get_default_llm_for_platform(platform_name: str) -> str:
    """Get the default model for a given platform."""
    defaults = {
        "ollama": "llama3",
        "vllm": "meta-llama/Llama-3.1-8B-Instruct",
        "lmstudio": "llama3.2",
    }
    return defaults.get(platform_name, "llama3")


# ============================================================================
# Image Processing
# ============================================================================


def decode_upload_file(content: bytes) -> np.ndarray:
    """Decode uploaded file content to OpenCV image."""
    img_array = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        pil_img = Image.open(io.BytesIO(content))
        pil_img = pil_img.convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    return img


def preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    """
    Preprocess image for better OCR results.
    Focuses on de-speckling and contrast without destroying text.
    """
    if img_bgr is None:
        return img_bgr

    if img_bgr.dtype != np.uint8:
        img_bgr = img_bgr.astype(np.uint8)

    if len(img_bgr.shape) == 2:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
    elif img_bgr.shape[2] == 4:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

    h, w = img_bgr.shape[:2]
    if max(h, w) < 1400:
        s = 1400 / max(h, w)
        img_bgr = cv2.resize(img_bgr, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = np.ones((2, 2), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)

    return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)


# ============================================================================
# Authentication
# ============================================================================


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify API key if configured."""
    config = ApiConfig.from_env()
    if config.api_key is None:
        return True
    if x_api_key is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key != config.api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid API key")
    return True


# ============================================================================
# Lifespan (Startup/Shutdown)
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    print("=" * 60)
    print("Shoeshine API Server")
    print("=" * 60)
    print("Philosophy: This is NOT AI. Pure OCR document extraction.")
    print("No training, no retention, no embeddings stored.")
    print("=" * 60)

    app.state.start_time = time.time()

    config = ApiConfig.from_env()
    print(f"\nConfiguration:")
    print(f"  Host: {config.host}:{config.port}")
    print(f"  API Key: {'Configured' if config.api_key else 'Not configured'}")
    print(f"  Default OCR Engine: {config.default_ocr_engine}")
    print(f"  OCR Idle Timeout: {config.ocr_idle_timeout_seconds}s")
    print(
        f"  Admin API Key: {'Configured' if config.admin_api_key else 'Not configured'}"
    )

    app.state.ocr_service = OCRService(engine=config.default_ocr_engine)
    ocr_status = "Available" if app.state.ocr_service.available else "Failed"
    print(f"  OCR: {ocr_status}")

    app.state.ollama_service = None
    if config.ollama_url:
        from api_server import OllamaService

        app.state.ollama_service = OllamaService(config.ollama_url)
        ollama_status = (
            "Available" if app.state.ollama_service.is_available() else "Failed"
        )
        print(f"  Ollama: {ollama_status}")

    app.state.llm_platforms = detect_llm_platforms()
    if app.state.llm_platforms:
        print(f"  LLM Platforms: {len(app.state.llm_platforms)} detected")
        for platform in app.state.llm_platforms:
            print(f"    - {platform.name}: {len(platform.models)} models")
    else:
        print("  LLM Platforms: None detected (set SHOESHINE_OLLAMA_URL)")

    if not app.state.ocr_service.available:
        print("\n  WARNING: OCR not available!")
        print("  Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  Or ensure EasyOCR can download its models.")

    print("\nEndpoints:")
    print("  POST /extract/text   - Extract plain text")
    print("  POST /extract/bbox   - Extract text with bounding boxes")
    print("  POST /harvest        - Structured extraction (requires LLM)")
    print("  GET  /health         - Health check")
    print("  GET  /models         - List available models")
    print("  GET  /admin/platforms - List detected LLM platforms")
    print("  GET  /admin/status   - Detailed system status")
    print("  GET  /admin/hardware - Hardware information")
    print("  GET  /admin/resources - Current resource usage")
    print("  GET  /admin/diagnostics - Complete system diagnostics")
    print("=" * 60)

    yield

    print("\nShutting down...")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Shoeshine API",
    description="""
## Document Scanning Layer for Local LLMs

**Shoeshine** is a lightweight document-to-text translator using OCR techniques.

### Philosophy
- **This is NOT AI** - Pure OCR, no training, no retention
- **Model-agnostic** - Output works with any local model (Ollama, Bedrock, LM Studio)
- **Zero data retention** - Documents are never stored

### OCR Engines
- **EasyOCR**: Default, pure Python (~300MB models on first run)
- **Tesseract**: Requires system installation

### Quick Start
  ```bash
curl -X POST http://localhost:8000/extract/text \
  -F "document=@document.jpg"
```
    """,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    config = ApiConfig.from_env()
    ocr_available = app.state.ocr_service.available
    ollama_available = (
        app.state.ollama_service.is_available() if app.state.ollama_service else False
    )
    llm_platforms_count = len(getattr(app.state, "llm_platforms", []))

    all_healthy = ocr_available

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.utcnow().isoformat() + "Z",
        version="1.0.0",
        services={
            "ocr": ocr_available,
            "ollama": ollama_available,
            "llm_platforms": llm_platforms_count > 0,
        },
        ocr_engine=config.default_ocr_engine,
    )


@app.get("/models", response_model=ModelsResponse, tags=["Models"])
async def list_models() -> ModelsResponse:
    """List available models."""
    return ModelsResponse(
        data=[
            ModelInfo(id="shoeshine-ocr", owned_by="shoeshine"),
            ModelInfo(id="shoeshine-harvest", owned_by="shoeshine"),
            ModelInfo(id="ollama", owned_by="ollama"),
        ]
    )


@app.post("/extract/text", response_model=ExtractResponse, tags=["Extraction"])
async def extract_text(
    document: UploadFile = File(..., description="Document file (image or PDF)"),
    language: str = Form("en", description="Language code"),
    preprocess: bool = Form(True, description="Apply image preprocessing"),
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
) -> ExtractResponse:
    """Extract plain text from a document."""
    start_time = time.time()
    verify_api_key(x_api_key)

    if not app.state.ocr_service.available:
        raise HTTPException(
            status_code=503,
            detail="OCR not available. Install Tesseract or ensure EasyOCR models are downloaded.",
        )

    try:
        content = await document.read()
        img = decode_upload_file(content)
        await document.seek(0)

        if preprocess:
            img = preprocess_for_ocr(img)

        result = app.state.ocr_service.process(img)

        if not result["success"]:
            raise HTTPException(
                status_code=500, detail=f"Extraction failed: {result.get('error')}"
            )

        processing_time = int((time.time() - start_time) * 1000)

        bbox_items = [
            BBoxItem(
                text=item["text"], confidence=item["confidence"], bbox=item["bbox"]
            )
            for item in result["items"]
        ]

        return ExtractResponse(
            success=True,
            text=result["text"],
            items=bbox_items,
            processing_time_ms=processing_time,
            usage=UsageInfo.from_text(result["text"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@app.post("/extract/bbox", response_model=ExtractResponse, tags=["Extraction"])
async def extract_with_bbox(
    document: UploadFile = File(..., description="Document file"),
    language: str = Form("en"),
    preprocess: bool = Form(True),
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
) -> ExtractResponse:
    """Extract text with bounding box coordinates."""
    start_time = time.time()
    verify_api_key(x_api_key)

    if not app.state.ocr_service.available:
        raise HTTPException(status_code=503, detail="OCR not available")

    try:
        content = await document.read()
        img = decode_upload_file(content)
        await document.seek(0)

        if preprocess:
            img = preprocess_for_ocr(img)

        result = app.state.ocr_service.process(img)

        if not result["success"]:
            raise HTTPException(
                status_code=500, detail=f"Extraction failed: {result.get('error')}"
            )

        processing_time = int((time.time() - start_time) * 1000)

        bbox_items = [
            BBoxItem(
                text=item["text"], confidence=item["confidence"], bbox=item["bbox"]
            )
            for item in result["items"]
        ]

        return ExtractResponse(
            success=True,
            text=result["text"],
            items=bbox_items,
            processing_time_ms=processing_time,
            usage=UsageInfo.from_text(result["text"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@app.post("/harvest", response_model=HarvestResponse, tags=["Extraction"])
async def harvest_document(
    document: UploadFile = File(..., description="Document file"),
    fields: str = Form("", description="Comma-separated fields to extract"),
    system_prompt: Optional[str] = Form(None, description="Custom system prompt"),
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
) -> HarvestResponse:
    """Extract structured key-value pairs from document."""
    start_time = time.time()
    verify_api_key(x_api_key)

    config = ApiConfig.from_env()

    if not app.state.ocr_service.available:
        raise HTTPException(status_code=503, detail="OCR not available")

    llm_available = (
        app.state.ollama_service.is_available() if app.state.ollama_service else False
    ) or len(getattr(app.state, "llm_platforms", [])) > 0

    if not llm_available:
        raise HTTPException(
            status_code=503,
            detail="No LLM configured. Set SHOESHINE_OLLAMA_URL or ensure Ollama/vLLM/LM Studio is running.",
        )

    try:
        content = await document.read()
        img = decode_upload_file(content)
        await document.seek(0)

        img = preprocess_for_ocr(img)

        ocr_result = app.state.ocr_service.process(img)

        if not ocr_result["success"]:
            raise HTTPException(
                status_code=500, detail=f"OCR failed: {ocr_result.get('error')}"
            )

        field_list = [f.strip() for f in fields.split(",") if f.strip()]

        items = []
        if app.state.ollama_service and app.state.ollama_service.is_available():
            items = app.state.ollama_service.extract_structured(
                ocr_result["text"], field_list, system_prompt
            )

        harvest_items = [
            HarvestItem(
                key=item.get("key", ""),
                value=item.get("value", ""),
                where=item.get("where"),
            )
            for item in items
        ]

        processing_time = int((time.time() - start_time) * 1000)

        return HarvestResponse(
            success=True,
            items=harvest_items,
            processing_time_ms=processing_time,
            usage=UsageInfo.from_text(ocr_result["text"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Harvest failed: {str(e)}")


# ============================================================================
# Admin Endpoints
# ============================================================================


class PlatformInfo(BaseModel):
    """Information about a detected LLM platform."""

    name: str
    url: str
    models: List[str]
    available: bool


class StatusResponse(BaseModel):
    """System status response."""

    status: str
    timestamp: str
    version: str = "1.0.0"
    ocr_engine: str
    ocr_available: bool
    llm_platforms: List[PlatformInfo]
    uptime_seconds: float


@app.get("/admin/platforms", response_model=List[PlatformInfo], tags=["Admin"])
async def list_platforms(
    x_admin_key: Optional[str] = Header(None, description="Admin API key"),
) -> List[PlatformInfo]:
    """List detected LLM platforms."""
    config = ApiConfig.from_env()
    if config.admin_api_key and x_admin_key != config.admin_api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid admin API key")

    platforms = getattr(app.state, "llm_platforms", [])
    return [
        PlatformInfo(
            name=p.name,
            url=p.url,
            models=p.models,
            available=True,
        )
        for p in platforms
    ]


@app.get("/admin/status", response_model=StatusResponse, tags=["Admin"])
async def system_status(
    x_admin_key: Optional[str] = Header(None, description="Admin API key"),
) -> StatusResponse:
    """Get detailed system status."""
    config = ApiConfig.from_env()
    if config.admin_api_key and x_admin_key != config.admin_api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid admin API key")

    platforms = getattr(app.state, "llm_platforms", [])
    ocr_available = (
        app.state.ocr_service.available if hasattr(app.state, "ocr_service") else False
    )

    uptime = time.time() - getattr(app.state, "start_time", time.time())

    return StatusResponse(
        status="healthy" if ocr_available else "degraded",
        timestamp=datetime.utcnow().isoformat() + "Z",
        ocr_engine=config.default_ocr_engine,
        ocr_available=ocr_available,
        llm_platforms=[
            PlatformInfo(
                name=p.name,
                url=p.url,
                models=p.models,
                available=True,
            )
            for p in platforms
        ],
        uptime_seconds=uptime,
    )


class HardwareInfoResponse(BaseModel):
    """Hardware information response."""

    timestamp: str
    platform: str
    python_version: str
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    gpus: List[Dict[str, Any]]


@app.get("/admin/hardware", response_model=HardwareInfoResponse, tags=["Admin"])
async def get_hardware_info(
    x_admin_key: Optional[str] = Header(None, description="Admin API key"),
) -> HardwareInfoResponse:
    """Get detailed hardware information."""
    config = ApiConfig.from_env()
    if config.admin_api_key and x_admin_key != config.admin_api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid admin API key")

    from system_info import get_hardware_info

    hw = get_hardware_info()

    return HardwareInfoResponse(
        timestamp=hw.timestamp,
        platform=hw.platform,
        python_version=hw.python_version,
        cpu={
            "cores": hw.cpu.cores,
            "threads": hw.cpu.threads,
            "brand": hw.cpu.brand,
            "frequency_mhz": hw.cpu.frequency_mhz,
            "usage_percent": hw.cpu.usage_percent,
        },
        memory={
            "total_gb": hw.memory.total_gb,
            "available_gb": hw.memory.available_gb,
            "used_percent": hw.memory.used_percent,
        },
        gpus=[
            {
                "name": g.name,
                "vram_gb": g.vram_gb,
                "compute_cap": g.compute_cap,
                "cuda_available": g.cuda_available,
                "usage_percent": g.usage_percent,
            }
            for g in hw.gpus
        ],
    )


class ResourceUsageResponse(BaseModel):
    """Resource usage response."""

    timestamp: str
    cpu_percent: float
    memory_percent: float
    gpu_percent: List[Dict[str, Any]]


@app.get("/admin/resources", response_model=ResourceUsageResponse, tags=["Admin"])
async def get_resource_usage(
    x_admin_key: Optional[str] = Header(None, description="Admin API key"),
) -> ResourceUsageResponse:
    """Get current resource usage."""
    config = ApiConfig.from_env()
    if config.admin_api_key and x_admin_key != config.admin_api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid admin API key")

    from system_info import get_resource_usage

    usage = get_resource_usage()

    return ResourceUsageResponse(
        timestamp=usage["timestamp"],
        cpu_percent=usage["cpu_percent"],
        memory_percent=usage["memory_percent"],
        gpu_percent=usage["gpu_percent"],
    )


class DiagnosticsResponse(BaseModel):
    """Complete diagnostics response."""

    timestamp: str
    hardware: Dict[str, Any]
    frameworks: List[Dict[str, Any]]
    dependencies: Dict[str, Dict[str, Any]]
    resource_usage: Dict[str, Any]
    recommendations: Dict[str, Any]


@app.get("/admin/diagnostics", response_model=DiagnosticsResponse, tags=["Admin"])
async def get_diagnostics(
    x_admin_key: Optional[str] = Header(None, description="Admin API key"),
) -> DiagnosticsResponse:
    """Run complete system diagnostics."""
    config = ApiConfig.from_env()
    if config.admin_api_key and x_admin_key != config.admin_api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid admin API key")

    from system_info import run_diagnostics

    diag = run_diagnostics()

    return DiagnosticsResponse(**diag)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    config = ApiConfig.from_env()
    uvicorn.run(
        "api_server:app",
        host=config.host,
        port=config.port,
        reload=True,
        log_level="info",
    )

# ============================================================================
# AWS Lambda Handler
# ============================================================================

try:
    from mangum import Mangum

    lambda_handler = Mangum(app, lifespan="off")
except ImportError:
    lambda_handler = None
    print("WARNING: mangum not installed - Lambda deployment unavailable")
