"""Data models for Shoeshine API."""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_text(cls, text: str):
        """Estimate tokens from text (roughly 4 chars per token)."""
        estimated_tokens = max(1, len(text) // 4)
        return cls(prompt_tokens=estimated_tokens, total_tokens=estimated_tokens)


class ExtractRequest(BaseModel):
    """Request model for text extraction."""

    document: Optional[str] = None
    language: str = "en"
    preprocess: bool = True
    return_bboxes: bool = False
    fields: Optional[List[str]] = None


class BBoxItem(BaseModel):
    """Bounding box item with text and coordinates."""

    text: str
    confidence: float
    bbox: List[int] = Field(..., min_length=4, max_length=4)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: List[int]) -> List[int]:
        """Validate bounding box coordinates [x1, y1, x2, y2]."""
        x1, y1, x2, y2 = v
        if x2 <= x1 or y2 <= y1:
            raise ValueError(
                "Invalid bounding box: x2 must be > x1 and y2 must be > y1"
            )
        return v


class CitationItem(BaseModel):
    """Citation item for extracted text."""

    text: str
    confidence: float = 1.0
    page: Optional[int] = None
    bbox: Optional[List[int]] = None


class ExtractResponse(BaseModel):
    """Response model for text extraction."""

    id: str = Field(default_factory=lambda: f"shoe-{uuid.uuid4().hex[:12]}")
    success: bool
    text: str = ""
    processing_time_ms: float = 0.0
    citations: List[CitationItem] = []
    usage: Optional[UsageInfo] = None

    model_config = {"json_encoders": {uuid.UUID: str}}


class ExtractBboxResponse(BaseModel):
    """Response model for text extraction with bounding boxes."""

    success: bool
    text: str = ""
    bboxes: List[BBoxItem] = []
    processing_time_ms: float = 0.0


class HarvestItem(BaseModel):
    """Harvested data item."""

    key: str
    value: str
    where: Optional[str] = None
    note: Optional[str] = None


class HarvestResponse(BaseModel):
    """Response model for data harvesting."""

    success: bool
    extracted: Dict[str, str] = {}
    items: List[HarvestItem] = []
    processing_time_ms: float = 0.0


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: str
    version: str
    environment: str
    services: Dict[str, bool] = {}


class ErrorResponse(BaseModel):
    """Response model for errors."""

    type: str
    message: str
    code: str
    details: Optional[Dict[str, Any]] = None
