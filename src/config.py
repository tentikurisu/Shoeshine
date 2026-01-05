"""Configuration module for Shoeshine."""

import os
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Environment(str, Enum):
    """Environment types."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ServerOptions(BaseModel):
    """Server configuration options."""

    port: int = 8000
    host: str = "0.0.0.0"
    log_level: str = "INFO"


class OCROptions(BaseModel):
    """OCR engine configuration options."""

    engine: str = "paddleocr"
    language: str = "en"
    min_confidence: float = 0.0
    use_gpu: bool = False


class BedrockOptions(BaseModel):
    """AWS Bedrock configuration options."""

    region: str = "us-east-1"
    model_id: str = "anthropic.claude-sonnet-4-20250507"
    max_tokens: int = 4096
    temperature: float = 0.0


class StorageOptions(BaseModel):
    """Storage configuration options."""

    s3_bucket: Optional[str] = None
    s3_prefix: str = "documents/"
    dynamodb_table: Optional[str] = None
    retention_hours: int = 24


class Settings(BaseModel):
    """Main application settings."""

    environment: Environment = Environment.LOCAL
    version: str = "1.0.0"
    server: ServerOptions = ServerOptions()
    ocr: OCROptions = OCROptions()
    bedrock: BedrockOptions = BedrockOptions()
    storage: StorageOptions = StorageOptions()

    def __init__(self, **kwargs):
        """Initialize settings with environment variable overrides."""
        if "environment" not in kwargs:
            env_str = os.getenv("SHOESHINE_ENV", "local").lower()
            kwargs["environment"] = Environment(env_str)
        super().__init__(**kwargs)

    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.environment == Environment.LOCAL

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
