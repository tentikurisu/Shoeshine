"""
Tests for Shoeshine API Server (Local-Only version).
"""

import pytest
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from io import BytesIO
from PIL import Image, ImageDraw


@pytest.fixture
def client():
    """Create a test client with initialized services."""
    from api_server import app, OCRService, OllamaService

    client = TestClient(app)

    app.state.ocr_service = OCRService(engine="easyocr")
    app.state.ollama_service = None  # May not be running in tests

    return client


@pytest.fixture
def sample_image():
    """Create a simple test image."""
    img = Image.new("RGB", (200, 100), color="white")
    draw = ImageDraw.Draw(img)

    draw.text((10, 30), "Test Document", fill="black")
    draw.text((10, 60), "Bank Name: Test Bank", fill="black")
    draw.text((10, 80), "Account: 12345678", fill="black")

    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return img_bytes.read(), "test.jpg"


def test_health_endpoint(client):
    """Test health endpoint returns correct structure."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ["healthy", "degraded"]
    assert "timestamp" in data
    assert "version" in data
    assert "services" in data
    assert "ocr" in data["services"]


def test_models_endpoint(client):
    """Test models endpoint returns correct structure."""
    response = client.get("/models")

    assert response.status_code == 200
    data = response.json()

    assert data["object"] == "list"
    assert "data" in data
    assert len(data["data"]) > 0


def test_extract_text_success(client, sample_image):
    """Test extract text returns successful response."""
    image_bytes, filename = sample_image

    response = client.post(
        "/extract/text", files={"document": (filename, image_bytes, "image/jpeg")}
    )

    assert response.status_code == 200
    result = response.json()

    assert result["success"] is True
    assert "text" in result
    assert len(result["text"]) > 0
    assert "processing_time_ms" in result
    assert result["processing_time_ms"] > 0


def test_extract_text_no_document(client):
    """Test extract text returns 422 when no document."""
    response = client.post("/extract/text")

    assert response.status_code == 422


def test_extract_bbox_success(client, sample_image):
    """Test extract with bboxes returns successful response."""
    image_bytes, filename = sample_image

    response = client.post(
        "/extract/bbox", files={"document": (filename, image_bytes, "image/jpeg")}
    )

    assert response.status_code == 200
    result = response.json()

    assert result["success"] is True
    assert "items" in result
    assert len(result["items"]) > 0
    assert "text" in result

    for item in result["items"]:
        assert "text" in item
        assert "bbox" in item
        assert len(item["bbox"]) == 4
        assert item["confidence"] >= 0.0
        assert item["confidence"] <= 1.0


def test_harvest_success(client, sample_image):
    """Test harvest returns successful response (requires LLM)."""
    image_bytes, filename = sample_image

    response = client.post(
        "/harvest",
        files={"document": (filename, image_bytes, "image/jpeg")},
        data={"fields": "bank_name, account_number"},
    )

    # Just check that it processes, not requiring success (Ollama may not be available)
    assert response.status_code in [200, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
