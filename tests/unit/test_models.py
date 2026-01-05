"""Unit tests for Shoeshine models."""

import pytest
from datetime import datetime

from src.models import (
    ExtractRequest,
    ExtractResponse,
    ExtractBboxResponse,
    HarvestResponse,
    HealthResponse,
    ErrorResponse,
    UsageInfo,
    BBoxItem,
    CitationItem,
    HarvestItem,
)


class TestUsageInfo:
    """Tests for UsageInfo model."""

    def test_from_text(self):
        """Test token estimation from text."""
        usage = UsageInfo.from_text("Hello world this is a test")
        # Rough estimate: 24 chars / 4 = 6 tokens
        assert usage.prompt_tokens == 6
        assert usage.total_tokens == 6


class TestExtractRequest:
    """Tests for ExtractRequest model."""

    def test_minimal_request(self):
        """Test minimal extract request."""
        request = ExtractRequest()
        assert request.language == "en"
        assert request.preprocess is True
        assert request.return_bboxes is False

    def test_full_request(self):
        """Test full extract request with all fields."""
        request = ExtractRequest(
            document="base64encodeddata",
            language="es",
            preprocess=True,
            return_bboxes=True,
            fields=["invoice_number", "total"],
        )
        assert request.language == "es"
        assert request.return_bboxes is True
        assert request.fields == ["invoice_number", "total"]


class TestExtractResponse:
    """Tests for ExtractResponse model."""

    def test_response_creation(self):
        """Test creating an extract response."""
        response = ExtractResponse(
            success=True,
            text="Hello world",
            processing_time_ms=100,
        )
        assert response.success is True
        assert response.text == "Hello world"
        assert response.id.startswith("shoe-")
        assert response.processing_time_ms == 100

    def test_response_with_citations(self):
        """Test response with citations."""
        citations = [
            CitationItem(text="Hello", confidence=0.99),
            CitationItem(text="world", confidence=0.98),
        ]
        response = ExtractResponse(
            success=True,
            text="Hello world",
            citations=citations,
        )
        assert len(response.citations) == 2


class TestBBoxItem:
    """Tests for BBoxItem model."""

    def test_bbox_creation(self):
        """Test creating a BBox item."""
        item = BBoxItem(
            text="Invoice #123",
            confidence=0.95,
            bbox=[100, 50, 300, 80],
        )
        assert item.text == "Invoice #123"
        assert item.confidence == 0.95
        assert item.bbox == [100, 50, 300, 80]

    def test_invalid_bbox(self):
        """Test invalid bbox raises error."""
        with pytest.raises(ValueError):
            BBoxItem(
                text="Test",
                confidence=1.0,
                bbox=[300, 80, 100, 50],  # x2 < x1, y2 < y1
            )


class TestHarvestItem:
    """Tests for HarvestItem model."""

    def test_harvest_item_creation(self):
        """Test creating a harvest item."""
        item = HarvestItem(
            key="invoice_number",
            value="INV-2024-001",
            where="Page 1, top right",
            note="Found in header",
        )
        assert item.key == "invoice_number"
        assert item.value == "INV-2024-001"
        assert item.where == "Page 1, top right"


class TestHarvestResponse:
    """Tests for HarvestResponse model."""

    def test_response_creation(self):
        """Test creating a harvest response."""
        items = [
            HarvestItem(key="total", value="$1,234.56"),
            HarvestItem(key="date", value="2024-01-15"),
        ]
        response = HarvestResponse(
            success=True,
            extracted={"total": "$1,234.56", "date": "2024-01-15"},
            items=items,
            processing_time_ms=500,
        )
        assert response.success is True
        assert len(response.items) == 2
        assert response.processing_time_ms == 500


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_healthy_response(self):
        """Test healthy response."""
        response = HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat() + "Z",
            version="1.0.0",
            environment="production",
            services={"ocr": True, "bedrock": True},
        )
        assert response.status == "healthy"
        assert response.services["ocr"] is True

    def test_degraded_response(self):
        """Test degraded response."""
        response = HealthResponse(
            status="degraded",
            timestamp=datetime.utcnow().isoformat() + "Z",
            version="1.0.0",
            environment="production",
            services={"ocr": False, "bedrock": True},
        )
        assert response.status == "degraded"


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response(self):
        """Test error response."""
        response = ErrorResponse(
            type="invalid_request_error",
            message="No document provided",
            code="400",
        )
        assert response.type == "invalid_request_error"
        assert response.message == "No document provided"
        assert response.code == "400"

    def test_error_with_details(self):
        """Test error with additional details."""
        response = ErrorResponse(
            type="validation_error",
            message="Invalid field",
            code="422",
            details={"field": "language", "reason": "Invalid value"},
        )
        assert response.details["field"] == "language"
