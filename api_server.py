"""
Shoeshine API Server - Document Scanning Layer for AWS Bedrock

A lightweight, model-agnostic document scanning service that translates
images/PDFs to structured text for consumption by AWS Bedrock.

Philosophy:
    This is NOT AI. It's a document-to-text translator using OCR techniques.
    No training, no retention, no embeddings stored. Pure extraction.

Usage:
    python api_server.py
    docker compose up --build

Environment Variables:
    # Deployment
    SHOESHINE_DEPLOY_MODE         - Deployment mode: lambda (default) or ecs
    SHOESHINE_ENV                 - Environment: local, lambda, ecs

    # Server
    SHOESHINE_HOST                - Host to bind (default: 0.0.0.0)
    SHOESHINE_PORT                - Port to listen (default: 8000)
    SHOESHINE_API_KEY             - API key for authentication (optional)

    # OCR Configuration
    SHOESHINE_DEFAULT_OCR_ENGINE  - Default engine: auto, docling, easyocr, textract, tesseract
    SHOESHINE_OCR_IDLE_TIMEOUT    - Idle timeout in seconds (default: 600)

    # Admin (for /admin endpoints)
    SHOESHINE_ADMIN_API_KEY       - Admin API key for OCR management endpoints

    # AWS
    AWS_REGION                    - AWS region for Bedrock and Textract
    AWS_ACCESS_KEY_ID             - AWS credentials (optional - uses IAM role in Lambda/ECS)
    AWS_SECRET_ACCESS_KEY         - AWS credentials (optional)
    BEDROCK_MODEL_ID              - Bedrock model ID (e.g., anthropic.claude-sonnet-4-20250507)
    ALLOWED_S3_BUCKETS            - Comma-separated S3 buckets for document retrieval

OCR Engines:
    Lambda:   textract, easyocr
    ECS/Local: docling, easyocr, textract, tesseract
"""

import os
import sys
import time
import uuid
import base64
import io
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import cv2
import numpy as np
import requests
import fitz
import boto3
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image
from pydantic import BaseModel, Field
from src.llm_clients import BedrockClient


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
    ocr_engine: str = "unknown"
    engine_loaded: bool = False


class HarvestItem(BaseModel):
    """Extracted item for harvest response."""

    key: str
    value: str
    where: Optional[str] = None
    confidence: Optional[float] = None


class HarvestResponse(BaseModel):
    """Harvest endpoint response."""

    success: bool
    extracted_text: Optional[str] = None
    answer: Optional[str] = None
    model: str
    processing_time_ms: float
    error: Optional[str] = None


class AskResponse(BaseModel):
    """Response for document Q&A."""

    success: bool
    id: str = Field(default_factory=lambda: f"shoe-{uuid.uuid4().hex[:8]}")
    object: str = "text_extraction.ask"
    created: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    question: str
    answer: str
    extracted_text: str
    llm: str = "bedrock"
    model: str = ""
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
    ocr_loaded_engine: Optional[str] = None
    ocr_idle_seconds: Optional[float] = None


# ============================================================================
# OCR Service Classes (Inline)
# ============================================================================


@dataclass
class ApiConfig:
    """API configuration from environment variables."""

    api_key: Optional[str]
    host: str
    port: int
    aws_region: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    bedrock_model_id: Optional[str]
    allowed_s3_buckets: str
    default_ocr_engine: str
    ocr_idle_timeout_seconds: int
    admin_api_key: Optional[str]

    @classmethod
    def from_env(cls) -> ApiConfig:
        return cls(
            api_key=os.getenv("SHOESHINE_API_KEY"),
            host=os.getenv("SHOESHINE_HOST", "0.0.0.0"),
            port=int(os.getenv("SHOESHINE_PORT", "8000")),
            aws_region=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", ""),
            allowed_s3_buckets=os.getenv("ALLOWED_S3_BUCKETS", ""),
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


class DoclingOCRService:
    """OCR service using Docling."""

    def __init__(self):
        try:
            from docling.document_converter import DocumentConverter

            self.converter = DocumentConverter()
            self.available = True
        except Exception as e:
            print(f"Docling initialization failed: {e}")
            self.converter = None
            self.available = False

    def process(self, content: bytes) -> Dict[str, Any]:
        """Process document content and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "Docling not available",
                "text": "",
                "items": [],
            }

        try:
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                result = self.converter.convert(tmp_path)
                text = result.document.export_to_text()

                items = []
                if hasattr(result.document, "export_to_dict"):
                    doc_dict = result.document.export_to_dict()
                    if "pages" in doc_dict:
                        for page in doc_dict["pages"]:
                            if "elements" in page:
                                for elem in page["elements"]:
                                    if "text" in elem:
                                        items.append(
                                            {
                                                "text": elem["text"],
                                                "confidence": 1.0,
                                                "bbox": elem.get("bbox", [0, 0, 0, 0]),
                                            }
                                        )

                return {"success": True, "text": text, "items": items}
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class TextractOCRService:
    """OCR service using AWS Textract."""

    def __init__(self):
        try:
            config = ApiConfig.from_env()
            self.client = boto3.client(
                "textract",
                region_name=config.aws_region or "us-east-1",
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key,
            )
            self.available = True
        except Exception as e:
            print(f"Textract initialization failed: {e}")
            self.client = None
            self.available = False

    def process(self, content: bytes) -> Dict[str, Any]:
        """Process image content and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "Textract not available",
                "text": "",
                "items": [],
            }

        try:
            response = self.client.detect_document_text(Document={"Bytes": content})

            items = []
            text_parts = []

            for block in response.get("Blocks", []):
                if block.get("BlockType") == "LINE":
                    text = block.get("Text", "")
                    text_parts.append(text)

                    geometry = block.get("Geometry", {})
                    bounding_box = geometry.get("BoundingBox", {})
                    items.append(
                        {
                            "text": text,
                            "confidence": block.get("Confidence", 0.0) / 100.0,
                            "bbox": [
                                int(bounding_box.get("Left", 0) * 1000),
                                int(bounding_box.get("Top", 0) * 1000),
                                int(
                                    (
                                        bounding_box.get("Left", 0)
                                        + bounding_box.get("Width", 0)
                                    )
                                    * 1000
                                ),
                                int(
                                    (
                                        bounding_box.get("Top", 0)
                                        + bounding_box.get("Height", 0)
                                    )
                                    * 1000
                                ),
                            ],
                        }
                    )

            text = " ".join(text_parts)
            return {"success": True, "text": text, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class OCRServiceFactory:
    """Factory for OCR services with single active engine mode."""

    def __init__(self):
        self.current_engine: Optional[str] = None
        self.current_service: Optional[Any] = None
        self.last_request_time: Dict[str, float] = {}
        self._is_lambda = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None

    def _get_available_engines(self) -> List[str]:
        """Get list of available engines for current environment."""
        if self._is_lambda:
            return ["textract", "easyocr"]
        return ["docling", "easyocr", "textract", "tesseract"]

    def _create_service(self, engine: str) -> Any:
        """Create a new OCR service instance."""
        if engine == "docling":
            if self._is_lambda:
                raise ValueError("Docling not available in Lambda (size constraints)")
            return DoclingOCRService()
        elif engine == "easyocr":
            return EasyOCRService()
        elif engine == "textract":
            return TextractOCRService()
        elif engine == "tesseract":
            if self._is_lambda:
                raise ValueError(
                    "Tesseract not available in Lambda (requires system binaries)"
                )
            return TesseractOCRService()
        else:
            raise ValueError(f"Unknown OCR engine: {engine}")

    def _unload_engine(self) -> bool:
        """Unload current engine if any."""
        if self.current_engine:
            print(f"Unloading OCR engine: {self.current_engine}")
            self.current_engine = None
            self.current_service = None
            return True
        return False

    def _load_engine(self, engine: str) -> None:
        """Load specified engine."""
        print(f"Loading OCR engine: {engine}")
        self.current_engine = engine
        self.current_service = self._create_service(engine)
        self.last_request_time[engine] = time.time()

    def get_service(self, engine: str) -> Any:
        """Get OCR service, loading engine if necessary."""
        if engine == "auto":
            engine_order = self._get_available_engines()
            for e in engine_order:
                try:
                    service = self.get_service(e)
                    if service.available:
                        return service
                except Exception as ex:
                    print(f"Engine {e} not available: {ex}")
                    continue
            raise RuntimeError("No OCR engine available")

        if self.current_engine != engine:
            self._unload_engine()
            self._load_engine(engine)

        self.last_request_time[engine] = time.time()
        return self.current_service

    def unload_current(self) -> Dict[str, Any]:
        """Explicitly unload current engine."""
        engine = self.current_engine
        unloaded = self._unload_engine()
        return {
            "success": unloaded,
            "unloaded_engine": engine,
            "message": f"Engine '{engine}' unloaded"
            if unloaded
            else "No engine was loaded",
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current OCR engine status."""
        idle_seconds = None
        if self.current_engine and self.current_engine in self.last_request_time:
            idle_seconds = time.time() - self.last_request_time[self.current_engine]

        return {
            "current_engine": self.current_engine,
            "idle_seconds": idle_seconds,
            "engines_used": list(self.last_request_time.keys()),
            "is_lambda": self._is_lambda,
        }

    def check_idle_timeout(self, timeout_seconds: int) -> bool:
        """Check if current engine should be unloaded due to inactivity."""
        if self._is_lambda:
            return False
        if not self.current_engine:
            return False

        last_time = self.last_request_time.get(self.current_engine, 0)
        idle_time = time.time() - last_time

        if idle_time >= timeout_seconds:
            print(
                f"OCR engine '{self.current_engine}' idle for {idle_time:.0f}s, unloading..."
            )
            self._unload_engine()
            return True
        return False


class BedrockService:
    """Service for AWS Bedrock integration."""

    def __init__(self):
        self.config = ApiConfig.from_env()
        self.client = None
        if self.config.aws_region and self.config.aws_access_key_id:
            self.client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.aws_region,
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
            )

    def is_available(self) -> bool:
        """Check if Bedrock is available."""
        return self.client is not None

    def extract_structured(
        self, text: str, fields: List[str], system_prompt: Optional[str] = None
    ) -> List[Dict]:
        """Extract structured data from text using Bedrock."""
        if not self.is_available():
            return []

        model_id = self.config.bedrock_model_id
        if not model_id:
            return []

        default_system = """You are extracting structured data from a document.
Extract requested fields as JSON array of objects.
Output format: [{"key": "field_name", "value": "extracted value", "where": "location"}]

If a field is not found, include it with value "NOT_FOUND"."""

        try:
            model_id_str: str = (
                model_id if isinstance(model_id, str) and model_id else ""
            )
            if not model_id_str:
                return []
            response = self.client.converse(
                modelId=model_id_str,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": f"Extract these fields: {', '.join(fields)}\n\nDocument:\n{text}"
                            }
                        ],
                    }
                ],
                system=[{"text": system_prompt or default_system}],
                inferenceConfig={"maxTokens": 4096, "temperature": 0.0},
            )

            content = response["output"]["message"]["content"][0]["text"]

            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "items" in data:
                    return data["items"]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass

        except Exception as e:
            print(f"Bedrock extraction failed: {e}")

        return []


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


def is_pdf_file(content: bytes) -> bool:
    """Check if file content is a PDF by magic bytes."""
    return content[:4] == b"%PDF"


def decode_pdf_pages(content: bytes) -> List[np.ndarray]:
    """Decode PDF content to list of OpenCV images (one per page)."""
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Invalid PDF file: {str(e)}")

    if doc.page_count == 0:
        raise ValueError("PDF has no pages")

    images = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3
        )
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        images.append(img_bgr)

    return images


def process_document_pages(
    images: List[np.ndarray], preprocess: bool = True, ocr_engine: str = "auto"
) -> Dict[str, Any]:
    """Process multiple document pages and combine results."""
    from api_server import app

    all_items = []
    all_text_parts = []
    has_errors = False
    error_msg = None

    ocr_service = app.state.ocr_factory.get_service(ocr_engine)

    for page_num, img in enumerate(images, start=1):
        if preprocess and ocr_engine not in ["docling"]:
            img = preprocess_for_ocr(img)

        if ocr_engine == "docling":
            result = ocr_service.process(img.tobytes())
        else:
            result = ocr_service.process(img)

        if not result["success"]:
            has_errors = True
            error_msg = result.get("error", "Unknown OCR error")
            continue

        page_marker = f"--- Page {page_num} ---"
        all_text_parts.append(page_marker)
        all_text_parts.append(result["text"])

        for item in result["items"]:
            item["text"] = f"{page_marker} {item['text']}"
            all_items.append(item)

    if not all_items and has_errors:
        return {"success": False, "error": error_msg, "text": "", "items": []}

    combined_text = "\n\n".join(all_text_parts)
    return {"success": True, "text": combined_text, "items": all_items}


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

    config = ApiConfig.from_env()
    print(f"\nConfiguration:")
    print(f"  Host: {config.host}:{config.port}")
    print(f"  API Key: {'Configured' if config.api_key else 'Not configured'}")
    print(f"  Default OCR Engine: {config.default_ocr_engine}")
    print(f"  OCR Idle Timeout: {config.ocr_idle_timeout_seconds}s")
    print(
        f"  Admin API Key: {'Configured' if config.admin_api_key else 'Not configured'}"
    )
    print(f"  Allowed S3 Buckets: {config.allowed_s3_buckets or 'None specified'}")
    print(f"  Bedrock: {'Configured' if config.aws_region else 'Not configured'}")

    app.state.ocr_factory = OCRServiceFactory()
    app.state.config = config
    print(f"  OCR Factory: Initialized")

    app.state.bedrock_service = BedrockService()
    bedrock_status = (
        "Available" if app.state.bedrock_service.is_available() else "Not configured"
    )
    print(f"  Bedrock: {bedrock_status}")

    app.state.bedrock_client = BedrockClient()
    print(
        f"  Bedrock Client: {'Available' if app.state.bedrock_client.is_available() else 'Not configured'}"
    )

    print("\nEndpoints:")
    print("  POST /extract/text   - Extract plain text (with ocr_engine param)")
    print("  POST /extract/bbox   - Extract text with bounding boxes")
    print("  POST /harvest        - Extract text + Bedrock Q&A")
    print("  POST /admin/ocr/unload - Unload current OCR engine")
    print("  GET  /admin/ocr/status - Get OCR engine status")
    print("  GET  /health         - Health check")
    print("  GET  /models         - List available models")
    print("=" * 60)

    yield

    print("\nShutting down...")
    app.state.ocr_factory.unload_current()


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Shoeshine API",
    description="""
## Document Scanning Layer for AWS Bedrock

**Shoeshine** is a lightweight document-to-text translator using OCR techniques.

### Philosophy
- **This is NOT AI** - Pure OCR, no training, no retention
- **AWS-Only** - Uses Bedrock for document Q&A
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
    config = app.state.config
    status = app.state.ocr_factory.get_status()
    bedrock_available = app.state.bedrock_service.is_available()

    return HealthResponse(
        status="healthy" if bedrock_available else "degraded",
        timestamp=datetime.utcnow().isoformat() + "Z",
        version="1.0.0",
        services={
            "ocr": status["current_engine"] is not None,
            "bedrock": bedrock_available,
        },
        ocr_engine=config.default_ocr_engine,
        ocr_loaded_engine=status["current_engine"],
        ocr_idle_seconds=status["idle_seconds"],
    )


@app.get("/models", response_model=ModelsResponse, tags=["Models"])
async def list_models() -> ModelsResponse:
    """List available models."""
    return ModelsResponse(
        data=[
            ModelInfo(id="shoeshine-ocr", owned_by="shoeshine"),
            ModelInfo(id="bedrock", owned_by="aws"),
        ]
    )


@app.post("/extract/text", response_model=ExtractResponse, tags=["Extraction"])
async def extract_text(
    document: UploadFile = File(..., description="Document file (image or PDF)"),
    language: str = Form("en", description="Language code"),
    preprocess: bool = Form(True, description="Apply image preprocessing"),
    ocr_engine: str = Form(
        "auto", description="OCR engine: docling, easyocr, textract, tesseract, auto"
    ),
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
) -> ExtractResponse:
    """Extract plain text from a document."""
    start_time = time.time()
    verify_api_key(x_api_key)

    try:
        content = await document.read()
        await document.seek(0)

        engine_was_loaded = app.state.ocr_factory.current_engine != ocr_engine
        ocr_service = app.state.ocr_factory.get_service(ocr_engine)

        if not ocr_service.available:
            raise HTTPException(
                status_code=503,
                detail=f"OCR engine '{ocr_engine}' not available.",
            )

        if is_pdf_file(content):
            images = decode_pdf_pages(content)
            result = process_document_pages(images, preprocess, ocr_engine)
        else:
            img = decode_upload_file(content)
            if preprocess and ocr_engine not in ["docling"]:
                img = preprocess_for_ocr(img)
            if ocr_engine == "docling":
                result = ocr_service.process(content)
            else:
                result = ocr_service.process(img)

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
            ocr_engine=app.state.ocr_factory.current_engine or ocr_engine,
            engine_loaded=engine_was_loaded,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@app.post("/extract/bbox", response_model=ExtractResponse, tags=["Extraction"])
async def extract_with_bbox(
    document: UploadFile = File(..., description="Document file (image or PDF)"),
    language: str = Form("en"),
    preprocess: bool = Form(True),
    ocr_engine: str = Form(
        "auto", description="OCR engine: docling, easyocr, textract, tesseract, auto"
    ),
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
) -> ExtractResponse:
    """Extract text with bounding box coordinates."""
    start_time = time.time()
    verify_api_key(x_api_key)

    try:
        content = await document.read()
        await document.seek(0)

        engine_was_loaded = app.state.ocr_factory.current_engine != ocr_engine
        ocr_service = app.state.ocr_factory.get_service(ocr_engine)

        if not ocr_service.available:
            raise HTTPException(
                status_code=503, detail=f"OCR engine '{ocr_engine}' not available"
            )

        if is_pdf_file(content):
            images = decode_pdf_pages(content)
            result = process_document_pages(images, preprocess, ocr_engine)
        else:
            img = decode_upload_file(content)
            if preprocess and ocr_engine not in ["docling"]:
                img = preprocess_for_ocr(img)
            if ocr_engine == "docling":
                result = ocr_service.process(content)
            else:
                result = ocr_service.process(img)

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
            ocr_engine=app.state.ocr_factory.current_engine or ocr_engine,
            engine_loaded=engine_was_loaded,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


class AdminOCRUnloadResponse(BaseModel):
    """Response for OCR unload endpoint."""

    success: bool
    unloaded_engine: Optional[str] = None
    message: str


class AdminOCRStatusResponse(BaseModel):
    """Response for OCR status endpoint."""

    current_engine: Optional[str] = None
    idle_seconds: Optional[float] = None
    engines_used: List[str] = []
    is_lambda: bool = False
    available_engines: List[str] = []
    note: Optional[str] = None


@app.post("/admin/ocr/unload", response_model=AdminOCRUnloadResponse, tags=["Admin"])
async def unload_ocr_engine(
    x_admin_api_key: Optional[str] = Header(
        None, description="Admin API key for authentication"
    ),
) -> AdminOCRUnloadResponse:
    """Explicitly unload the current OCR engine to free memory."""
    config = app.state.config
    if config.admin_api_key is None:
        raise HTTPException(status_code=501, detail="Admin API key not configured")
    if x_admin_api_key != config.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin API key")

    result = app.state.ocr_factory.unload_current()
    return AdminOCRUnloadResponse(
        success=result["success"],
        unloaded_engine=result["unloaded_engine"],
        message=result["message"],
    )


@app.get("/admin/ocr/status", response_model=AdminOCRStatusResponse, tags=["Admin"])
async def get_ocr_status(
    x_admin_api_key: Optional[str] = Header(
        None, description="Admin API key for authentication"
    ),
) -> AdminOCRStatusResponse:
    """Get current OCR engine status."""
    config = app.state.config
    if config.admin_api_key is None:
        raise HTTPException(status_code=501, detail="Admin API key not configured")
    if x_admin_api_key != config.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin API key")

    status = app.state.ocr_factory.get_status()
    return AdminOCRStatusResponse(
        current_engine=status["current_engine"],
        idle_seconds=status["idle_seconds"],
        engines_used=status["engines_used"],
        is_lambda=status.get("is_lambda", False),
        available_engines=app.state.ocr_factory._get_available_engines(),
    )


class HarvestRequest(BaseModel):
    """Harvest endpoint request."""

    document: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_key: Optional[str] = None
    question: str = "Summarize this document"
    prompt: str = (
        "Answer questions about this document based ONLY on the text extracted."
    )
    temperature: float = 0.0
    ocr_engine: str = "auto"


@app.post("/harvest", response_model=HarvestResponse, tags=["Extraction"])
async def harvest_document(
    request: HarvestRequest,
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
) -> HarvestResponse:
    """Extract text from document and send to Bedrock for Q&A."""
    start_time = time.time()
    verify_api_key(x_api_key)

    ocr_service = app.state.ocr_factory.get_service(request.ocr_engine)
    if not ocr_service.available:
        raise HTTPException(
            status_code=503, detail=f"OCR engine '{request.ocr_engine}' not available"
        )

    if not app.state.bedrock_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Bedrock not available. Configure AWS credentials.",
        )

    try:
        image_bytes = None
        if request.document:
            try:
                image_bytes = base64.b64decode(request.document)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 document")
        elif request.s3_bucket and request.s3_key:
            config = app.state.config
            allowed_buckets = (
                config.allowed_s3_buckets.split(",")
                if config.allowed_s3_buckets
                else []
            )
            if allowed_buckets and request.s3_bucket not in allowed_buckets:
                raise HTTPException(
                    status_code=403,
                    detail=f"S3 bucket '{request.s3_bucket}' not in allowed list",
                )
            try:
                s3_client = boto3.client("s3")
                response = s3_client.get_object(
                    Bucket=request.s3_bucket, Key=request.s3_key
                )
                image_bytes = response["Body"].read()
            except Exception as e:
                error_str = str(e)
                if "NoSuchKey" in error_str or "not found" in error_str.lower():
                    raise HTTPException(status_code=404, detail="S3 object not found")
                elif "NoSuchBucket" in error_str or "bucket" in error_str.lower():
                    raise HTTPException(status_code=404, detail="S3 bucket not found")
                else:
                    raise HTTPException(
                        status_code=403, detail=f"S3 access denied: {error_str}"
                    )
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either 'document' (base64) or 's3_bucket' + 's3_key'",
            )

        if not image_bytes:
            raise HTTPException(status_code=400, detail="No document content received")

        try:
            if request.ocr_engine == "docling":
                ocr_result = ocr_service.process(image_bytes)
            else:
                img = decode_upload_file(image_bytes)
                if request.ocr_engine not in ["docling"]:
                    img = preprocess_for_ocr(img)
                ocr_result = ocr_service.process(img)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"OCR extraction failed: {str(e)}"
            )

        if not ocr_result["success"]:
            raise HTTPException(
                status_code=500, detail=f"OCR failed: {ocr_result.get('error')}"
            )

        try:
            answer = app.state.bedrock_client.ask(
                text=ocr_result["text"],
                question=request.question,
                system_prompt=request.prompt,
                temperature=request.temperature,
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Bedrock request failed: {str(e)}"
            )

        return HarvestResponse(
            success=True,
            extracted_text=ocr_result["text"],
            answer=answer,
            model=app.state.bedrock_client.model_id,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Harvest failed: {str(e)}")


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
