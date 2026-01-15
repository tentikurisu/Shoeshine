"""
Tests for Shoeshine Local-Only API Server.

These tests verify:
- OCR engine selection
- LLM platform detection
- API endpoints
- Health checks
- Configuration loading
"""

import pytest
import sys
from io import BytesIO
from PIL import Image, ImageDraw
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from api_server import (
    app,
    OCRService,
    EasyOCRService,
    TesseractOCRService,
    OllamaService,
    LLMPlatform,
    detect_llm_platforms,
    ApiConfig,
    HealthResponse,
    ExtractResponse,
    HarvestResponse,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create a test client with initialized services."""
    test_client = TestClient(app)

    # Initialize OCR service
    app.state.ocr_service = OCRService(engine="easyocr")

    # No Ollama service in tests (optional)
    app.state.ollama_service = None
    app.state.llm_platforms = []

    return test_client


@pytest.fixture
def sample_image():
    """Create a simple test image with text."""
    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)

    # Add test text
    draw.text((20, 20), "Test Invoice", fill="black")
    draw.text((20, 50), "Bank Name: Test Bank", fill="black")
    draw.text((20, 80), "Account Number: 12345678", fill="black")
    draw.text((20, 110), "Total: $500.00", fill="black")

    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return img_bytes.read(), "test_invoice.jpg"


@pytest.fixture
def sample_pdf_bytes():
    """Create a simple PDF-like bytes (actually JPEG for testing)."""
    # Use the image fixture since we don't have PDF generation in tests
    img = Image.new("RGB", (200, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), "Test Document", fill="black")

    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return img_bytes.read(), "test.pdf"


# ============================================================================
# Configuration Tests
# ============================================================================


class TestApiConfig:
    """Tests for ApiConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ApiConfig.from_env()

        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.default_ocr_engine == "easyocr"
        assert config.ocr_idle_timeout_seconds == 600

    def test_env_override(self):
        """Test environment variable override."""
        with patch.dict(
            "os.environ",
            {
                "SHOESHINE_HOST": "127.0.0.1",
                "SHOESHINE_PORT": "9000",
                "SHOESHINE_DEFAULT_OCR_ENGINE": "docling",
                "SHOESHINE_OCR_IDLE_TIMEOUT": "300",
            },
        ):
            config = ApiConfig.from_env()

            assert config.host == "127.0.0.1"
            assert config.port == 9000
            assert config.default_ocr_engine == "docling"
            assert config.ocr_idle_timeout_seconds == 300

    def test_no_aws_fields(self):
        """Verify AWS fields are removed."""
        config = ApiConfig.from_env()

        assert not hasattr(config, "aws_region")
        assert not hasattr(config, "aws_access_key_id")
        assert not hasattr(config, "bedrock_model_id")

    def test_optional_fields(self):
        """Test optional fields can be None."""
        config = ApiConfig.from_env()

        assert config.api_key is None or isinstance(config.api_key, str)
        assert config.ollama_url is None or isinstance(config.ollama_url, str)
        assert config.llm_model is None or isinstance(config.llm_model, str)


# ============================================================================
# OCR Service Tests
# ============================================================================


class TestOCRService:
    """Tests for OCR service."""

    def test_easyocr_service_creation(self):
        """Test EasyOCR service can be created."""
        service = EasyOCRService()
        # Service may or may not be available depending on system
        assert hasattr(service, "available")
        assert hasattr(service, "reader")

    def test_tesseract_service_creation(self):
        """Test Tesseract service can be created."""
        service = TesseractOCRService()
        assert hasattr(service, "available")
        assert hasattr(service, "pytesseract") or not service.available

    def test_ocr_service_default(self):
        """Test OCR service with default engine."""
        service = OCRService(engine="easyocr")
        assert service.engine == "easyocr"
        assert hasattr(service, "primary")
        assert hasattr(service, "fallback")

    def test_ocr_service_with_fallback(self):
        """Test OCR service with fallback."""
        service = OCRService(engine="easyocr")
        # Primary should be available, fallback may or may not be
        assert service.primary is not None or service.fallback is not None


# ============================================================================
# LLM Platform Detection Tests
# ============================================================================


class TestLLMPlatform:
    """Tests for LLM platform detection."""

    def test_platform_creation(self):
        """Test LLMPlatform can be created."""
        platform = LLMPlatform(
            name="test", url="http://localhost:11434", models=["model1", "model2"]
        )

        assert platform.name == "test"
        assert platform.url == "http://localhost:11434"
        assert len(platform.models) == 2

    def test_platform_repr(self):
        """Test LLMPlatform string representation."""
        platform = LLMPlatform("ollama", "http://localhost", ["llama3"])
        repr_str = repr(platform)

        assert "ollama" in repr_str
        assert "1 models" in repr_str

    @patch("httpx.Client")
    def test_detect_no_platforms(self, mock_client):
        """Test detection when no platforms are available."""
        mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("Connection failed")

        platforms = detect_llm_platforms()

        assert isinstance(platforms, list)

    @patch("httpx.Client")
    def test_detect_ollama(self, mock_client):
        """Test Ollama detection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3"}, {"name": "mistral"}]
        }

        mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        platforms = detect_llm_platforms()

        # Should detect at least Ollama
        platform_names = [p.name for p in platforms]
        assert "ollama" in platform_names


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns correct structure."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "services" in data
        assert "ocr_engine" in data

        # Check services structure
        services = data["services"]
        assert "ocr" in services
        # May or may not have ollama depending on mock


class TestExtractEndpoints:
    """Tests for text extraction endpoints."""

    def test_extract_text_success(self, client, sample_image):
        """Test successful text extraction."""
        image_bytes, filename = sample_image

        response = client.post(
            "/extract/text", files={"document": (filename, image_bytes, "image/jpeg")}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "text" in data
        assert "items" in data
        assert data["model"] == "shoeshine-ocr"

    def test_extract_text_with_ocr_engine(self, client, sample_image):
        """Test extraction with specific OCR engine."""
        image_bytes, filename = sample_image

        response = client.post(
            f"/extract/text?ocr_engine=easyocr",
            files={"document": (filename, image_bytes, "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_extract_text_no_file(self, client):
        """Test extraction without file returns error."""
        response = client.post("/extract/text")

        assert response.status_code == 422  # Validation error

    def test_extract_bbox_success(self, client, sample_image):
        """Test extraction with bounding boxes."""
        image_bytes, filename = sample_image

        response = client.post(
            "/extract/bbox", files={"document": (filename, image_bytes, "image/jpeg")}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_extract_response_model(self):
        """Test ExtractResponse model."""
        response = ExtractResponse(success=True, text="Test text")

        assert response.success is True
        assert response.text == "Test text"
        assert response.model == "shoeshine-ocr"


class TestModelsEndpoint:
    """Tests for models endpoint."""

    def test_list_models(self, client):
        """Test listing available models."""
        response = client.get("/models")

        assert response.status_code == 200
        data = response.json()

        assert data["object"] == "list"
        assert "data" in data
        assert isinstance(data["data"], list)


# ============================================================================
# Harvest Endpoint Tests
# ============================================================================


class TestHarvestEndpoint:
    """Tests for harvest (structured extraction) endpoint."""

    def test_harvest_requires_llm(self, client, sample_image):
        """Test harvest fails without LLM configured."""
        image_bytes, filename = sample_image

        # No Ollama service configured in test
        response = client.post(
            "/harvest",
            files={"document": (filename, image_bytes, "image/jpeg")},
            data={"fields": "account_number,total"},
        )

        # Should fail because no LLM is available
        assert response.status_code == 503


# ============================================================================
# Admin Endpoints Tests
# ============================================================================


class TestAdminEndpoints:
    """Tests for admin endpoints."""

    def test_admin_platforms_endpoint(self, client):
        """Test admin platforms endpoint returns list."""
        response = client.get("/admin/platforms")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_admin_status_endpoint(self, client):
        """Test admin status endpoint returns status."""
        response = client.get("/admin/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ocr_engine" in data
        assert "ocr_available" in data
        assert "llm_platforms" in data
        assert "uptime_seconds" in data

    def test_admin_platforms_with_api_key(self, client):
        """Test admin platforms requires valid admin key."""
        from api_server import ApiConfig

        config = ApiConfig.from_env()
        if config.admin_api_key:
            response = client.get(
                "/admin/platforms", headers={"X-Admin-Key": "wrong_key"}
            )
            assert response.status_code == 403


# ============================================================================
# Image Processing Tests
# ============================================================================


class TestImageProcessing:
    """Tests for image processing functions."""

    def test_decode_upload_file(self, sample_image):
        """Test decoding uploaded file."""
        from api_server import decode_upload_file

        image_bytes, _ = sample_image
        img = decode_upload_file(image_bytes)

        assert img is not None
        assert len(img.shape) == 3  # BGR image

    def test_preprocess_for_ocr(self, sample_image):
        """Test OCR preprocessing."""
        from api_server import decode_upload_file, preprocess_for_ocr

        image_bytes, _ = sample_image
        img = decode_upload_file(image_bytes)
        processed = preprocess_for_ocr(img)

        assert processed is not None
        assert len(processed.shape) == 3


# ============================================================================
# Response Model Tests
# ============================================================================


class TestResponseModels:
    """Tests for API response models."""

    def test_health_response(self):
        """Test HealthResponse model."""
        response = HealthResponse(
            status="healthy",
            timestamp="2024-01-01T00:00:00Z",
            version="1.0.0",
            services={"ocr": True, "ollama": False},
            ocr_engine="easyocr",
        )

        assert response.status == "healthy"
        assert response.services["ocr"] is True

    def test_extract_response(self):
        """Test ExtractResponse model."""
        response = ExtractResponse(
            success=True,
            text="Test text",
            items=[],
        )

        assert response.success is True
        assert response.text == "Test text"
        assert response.model == "shoeshine-ocr"

    def test_harvest_response(self):
        """Test HarvestResponse model."""
        from api_server import HarvestItem

        items = [HarvestItem(key="test", value="value", where="page 1")]

        response = HarvestResponse(success=True, items=items, processing_time_ms=1000)

        assert response.success is True
        assert len(response.items) == 1
        assert response.items[0].key == "test"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for the complete flow."""

    def test_full_extraction_flow(self, client, sample_image):
        """Test complete extraction flow."""
        image_bytes, filename = sample_image

        # 1. Health check
        health = client.get("/health")
        assert health.status_code == 200

        # 2. Extract text
        extract = client.post(
            "/extract/text", files={"document": (filename, image_bytes, "image/jpeg")}
        )
        assert extract.status_code == 200
        assert extract.json()["success"] is True

        # 3. Extract with bbox
        bbox = client.post(
            "/extract/bbox", files={"document": (filename, image_bytes, "image/jpeg")}
        )
        assert bbox.status_code == 200
        assert bbox.json()["success"] is True

    def test_different_ocr_engines(self, client, sample_image):
        """Test switching between OCR engines."""
        image_bytes, filename = sample_image

        engines = ["easyocr"]

        for engine in engines:
            response = client.post(
                f"/extract/text?ocr_engine={engine}",
                files={"document": (filename, image_bytes, "image/jpeg")},
            )

            # Engine may or may not be available depending on system
            assert response.status_code in [200, 503]


# ============================================================================
# System Info Tests
# ============================================================================


class TestSystemInfo:
    """Tests for system_info module."""

    def test_hardware_info_structure(self):
        """Test hardware info returns valid structure."""
        from system_info import get_hardware_info

        hw = get_hardware_info()

        assert hasattr(hw, "cpu")
        assert hasattr(hw, "memory")
        assert hasattr(hw, "gpus")
        assert hasattr(hw, "platform")
        assert hasattr(hw, "python_version")
        assert hw.platform in ["Windows", "Linux", "macOS", ""]

    def test_cpu_info_structure(self):
        """Test CPU info has required fields."""
        from system_info import get_cpu_info

        cpu = get_cpu_info()

        assert hasattr(cpu, "cores")
        assert hasattr(cpu, "threads")
        assert hasattr(cpu, "brand")
        assert cpu.cores >= 0
        assert cpu.threads >= 0

    def test_memory_info_structure(self):
        """Test memory info has required fields."""
        from system_info import get_memory_info

        mem = get_memory_info()

        assert hasattr(mem, "total_gb")
        assert hasattr(mem, "available_gb")
        assert hasattr(mem, "used_percent")

    def test_get_resource_usage(self):
        """Test resource usage returns valid data."""
        from system_info import get_resource_usage

        usage = get_resource_usage()

        assert "timestamp" in usage
        assert "cpu_percent" in usage
        assert "memory_percent" in usage
        assert 0 <= usage["cpu_percent"] <= 100

    def test_detect_llm_frameworks(self):
        """Test LLM framework detection returns list."""
        from system_info import detect_llm_frameworks

        frameworks = detect_llm_frameworks()

        assert isinstance(frameworks, list)
        names = [f.name for f in frameworks]
        assert "ollama" in names
        assert "vllm" in names
        assert "lmstudio" in names

    def test_check_dependencies(self):
        """Test dependency checking returns valid structure."""
        from system_info import check_dependencies

        deps = check_dependencies()

        assert isinstance(deps, dict)
        for name, info in deps.items():
            assert "installed" in info

    def test_run_diagnostics(self):
        """Test diagnostics runs without error."""
        from system_info import run_diagnostics

        diag = run_diagnostics()

        assert "timestamp" in diag
        assert "hardware" in diag
        assert "frameworks" in diag
        assert "dependencies" in diag
        assert "recommendations" in diag

    def test_performance_recommendations(self):
        """Test performance recommendations based on hardware."""
        from system_info import get_hardware_info, get_performance_recommendations

        hw = get_hardware_info()
        recs = get_performance_recommendations(hw)

        assert "ocr_engine" in recs
        assert "batch_size" in recs
        assert "warnings" in recs
        assert recs["batch_size"] >= 1


class TestAdminHardwareEndpoints:
    """Tests for admin hardware endpoints."""

    def test_admin_hardware_endpoint(self, client):
        """Test admin hardware endpoint returns info."""
        response = client.get("/admin/hardware")
        assert response.status_code == 200
        data = response.json()
        assert "cpu" in data
        assert "memory" in data
        assert "gpus" in data
        assert "platform" in data

    def test_admin_resources_endpoint(self, client):
        """Test admin resources endpoint returns usage."""
        response = client.get("/admin/resources")
        assert response.status_code == 200
        data = response.json()
        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "timestamp" in data

    def test_admin_diagnostics_endpoint(self, client):
        """Test admin diagnostics endpoint returns full info."""
        response = client.get("/admin/diagnostics")
        assert response.status_code == 200
        data = response.json()
        assert "hardware" in data
        assert "frameworks" in data
        assert "dependencies" in data
        assert "recommendations" in data


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
