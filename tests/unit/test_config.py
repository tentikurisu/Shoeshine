"""Unit tests for Shoeshine configuration."""

import os
import pytest
import tempfile
import yaml

from src.config import (
    Settings,
    Environment,
    OCROptions,
    BedrockOptions,
    StorageOptions,
)


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.environment == Environment.LOCAL
        assert settings.version == "1.0.0"
        assert settings.server.port == 8000
        assert settings.ocr.language == "en"
        assert settings.bedrock.region == "eu-west-2"

    def test_environment_from_env(self):
        """Test environment loading from environment variable."""
        os.environ["SHOESHINE_ENV"] = "production"
        try:
            settings = Settings()
            assert settings.environment == Environment.PRODUCTION
        finally:
            del os.environ["SHOESHINE_ENV"]

    def test_is_local(self):
        """Test is_local method."""
        settings = Settings(environment=Environment.LOCAL)
        assert settings.is_local() is True

        settings = Settings(environment=Environment.PRODUCTION)
        assert settings.is_local() is False

    def test_is_production(self):
        """Test is_production method."""
        settings = Settings(environment=Environment.PRODUCTION)
        assert settings.is_production() is True

        settings = Settings(environment=Environment.LOCAL)
        assert settings.is_production() is False


class TestOCROptions:
    """Tests for OCR options."""

    def test_default_ocr_options(self):
        """Test default OCR options."""
        options = OCROptions()
        assert options.engine == "paddleocr"
        assert options.language == "en"
        assert options.min_confidence == 0.0
        assert options.use_gpu is False

    def test_custom_ocr_options(self):
        """Test custom OCR options."""
        options = OCROptions(
            engine="tesseract",
            language="es",
            min_confidence=0.5,
            use_gpu=True,
        )
        assert options.engine == "tesseract"
        assert options.language == "es"
        assert options.min_confidence == 0.5
        assert options.use_gpu is True


class TestBedrockOptions:
    """Tests for Bedrock options."""

    def test_default_bedrock_options(self):
        """Test default Bedrock options."""
        options = BedrockOptions()
        assert options.region == "eu-west-2"
        assert options.model_id == "anthropic.claude-sonnet-4-20250507"
        assert options.max_tokens == 4096
        assert options.temperature == 0.0

    def test_custom_bedrock_options(self):
        """Test custom Bedrock options."""
        options = BedrockOptions(
            region="ap-southeast-1",
            model_id="anthropic.claude-3-sonnet-20240229",
            temperature=0.5,
        )
        assert options.region == "ap-southeast-1"
        assert options.temperature == 0.5


class TestStorageOptions:
    """Tests for Storage options."""

    def test_default_storage_options(self):
        """Test default storage options."""
        options = StorageOptions()
        assert options.s3_bucket is None
        assert options.s3_prefix == "documents/"
        assert options.dynamodb_table is None
        assert options.retention_hours == 24

    def test_custom_storage_options(self):
        """Test custom storage options."""
        options = StorageOptions(
            s3_bucket="my-bucket",
            dynamodb_table="my-table",
            retention_hours=168,
        )
        assert options.s3_bucket == "my-bucket"
        assert options.dynamodb_table == "my-table"
        assert options.retention_hours == 168
