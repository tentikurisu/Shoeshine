"""
Integration tests for LLM model swapping functionality.

This test suite verifies:
- Bedrock model discovery and caching
- Model validation with capability checks
- Admin endpoints functionality
- Harvest endpoint model selection
- Error handling and logging
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from src.config import BedrockOptions, Settings
from src.llm_clients import BedrockClient
from api_server import app, BedrockModelFactory


class TestBedrockSwapping:
    """Test suite for LLM model swapping functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return Settings(
            bedrock=BedrockOptions(
                region="us-east-1",
                model_id="anthropic.claude-sonnet-4-20250507",
                model_cache_ttl=3600,
            )
        )

    @pytest.fixture
    def mock_bedrock_models(self):
        """Mock Bedrock models response."""
        return [
            {
                "modelId": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "modelName": "Claude 3.5 Sonnet",
                "providerName": "Anthropic",
                "inputModalities": ["TEXT", "IMAGE"],
                "outputModalities": ["TEXT"],
                "responseStreamingSupported": True,
                "modelLifecycle": {"status": "ACTIVE"},
            },
            {
                "modelId": "meta.llama3-1-405b-instruct-v1:0",
                "modelName": "Llama 3.1 405B Instruct",
                "providerName": "Meta",
                "inputModalities": ["TEXT"],
                "outputModalities": ["TEXT"],
                "responseStreamingSupported": True,
                "modelLifecycle": {"status": "ACTIVE"},
            },
            {
                "modelId": "amazon.titan-text-premier-v1:0",
                "modelName": "Titan Text Premier",
                "providerName": "Amazon",
                "inputModalities": ["TEXT"],
                "outputModalities": ["TEXT"],
                "responseStreamingSupported": True,
                "modelLifecycle": {"status": "ACTIVE"},
            },
        ]

    class TestBedrockClient:
        """Test Bedrock client model switching."""

        @patch("src.llm_clients.boto3.client")
        def test_model_validation_success(
            self, mock_boto3, mock_config, mock_bedrock_models
        ):
            """Test successful model validation."""
            # Setup mock
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": mock_bedrock_models
            }

            client = BedrockClient(region="us-east-1")

            # Test valid model
            assert (
                client.validate_model("anthropic.claude-3-5-sonnet-20240620-v1:0")
                is True
            )
            assert client.validate_model("meta.llama3-1-405b-instruct-v1:0") is True

        @patch("src.llm_clients.boto3.client")
        def test_model_validation_invalid_model(self, mock_boto3, mock_config):
            """Test invalid model rejection."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": [
                    {
                        "modelId": "valid.model",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["TEXT"],
                        "responseStreamingSupported": True,
                    }
                ]
            }

            client = BedrockClient(region="us-east-1")

            # Test invalid model
            assert client.validate_model("invalid.model.id") is False
            assert client.validate_model("") is False

        @patch("src.llm_clients.boto3.client")
        def test_model_validation_capability_checks(self, mock_boto3, mock_config):
            """Test model validation checks capabilities."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            # Model without TEXT input/output
            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": [
                    {
                        "modelId": "embedding.model",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["EMBEDDING"],
                        "responseStreamingSupported": False,
                    }
                ]
            }

            client = BedrockClient(region="us-east-1")
            assert client.validate_model("embedding.model") is False

        @patch("src.llm_clients.boto3.client")
        def test_set_model(self, mock_boto3, mock_config):
            """Test model setting."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            client = BedrockClient(region="us-east-1")

            # Test setting valid model
            result = client.set_model("anthropic.claude-3-5-sonnet-20240620-v1:0")
            assert result is True
            assert (
                client.current_model_id == "anthropic.claude-3-5-sonnet-20240620-v1:0"
            )

    class TestBedrockModelFactory:
        """Test Bedrock model factory."""

        def test_initialization(self, mock_config):
            """Test factory initialization."""
            factory = BedrockModelFactory(mock_config)
            assert factory.config == mock_config
            assert factory.available_models == []
            assert factory.models_used == []

        @patch("src.llm_clients.boto3.client")
        def test_get_available_models_cache_miss(
            self, mock_boto3, mock_config, mock_bedrock_models
        ):
            """Test model discovery on cache miss."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": mock_bedrock_models
            }

            factory = BedrockModelFactory(mock_config)
            factory.last_cache_update = 0  # Force cache miss

            models = factory.get_available_models()

            assert len(models) == 3
            assert factory.available_models == models
            assert factory.last_cache_update > 0

        @patch("src.llm_clients.boto3.client")
        def test_get_available_models_cache_hit(
            self, mock_boto3, mock_config, mock_bedrock_models
        ):
            """Test model discovery on cache hit."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            factory = BedrockModelFactory(mock_config)

            # Prime cache
            factory.available_models = mock_bedrock_models
            factory.last_cache_update = time.time()

            models = factory.get_available_models()

            # Should not call API again
            mock_bedrock.list_foundation_models.assert_not_called()
            assert models == mock_bedrock_models

        @patch("src.llm_clients.boto3.client")
        def test_refresh_models(self, mock_boto3, mock_config, mock_bedrock_models):
            """Test model cache refresh."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": mock_bedrock_models
            }

            factory = BedrockModelFactory(mock_config)
            result = factory.refresh_models()

            assert result["success"] is True
            assert result["models_before"] == 0
            assert result["models_after"] == 3

        def test_get_status(self, mock_config):
            """Test factory status reporting."""
            factory = BedrockModelFactory(mock_config)
            factory.models_used = ["model1", "model2"]
            factory.last_cache_update = time.time()

            status = factory.get_status()

            assert status["models_used"] == ["model1", "model2"]
            assert status["available_models_count"] == 0
            assert "cache_age_seconds" in status

    class TestAdminEndpoints:
        """Test admin endpoints for LLM management."""

        def test_bedrock_status_endpoint(self, mock_config):
            """Test /admin/bedrock/status endpoint."""
            client = TestClient(app)

            # Setup app state
            app.state.config = mock_config
            app.state.bedrock_factory = BedrockModelFactory(mock_config)
            app.state.bedrock_client = Mock()
            app.state.bedrock_client.default_model_id = "test.model"

            response = client.get(
                "/admin/bedrock/status", headers={"x-admin-api-key": "test-key"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["current_model"] == "test.model"
            assert "available_models_count" in data

        def test_bedrock_models_refresh_endpoint(
            self, mock_config, mock_bedrock_models
        ):
            """Test /admin/bedrock/models endpoint."""
            with patch("src.llm_clients.boto3.client") as mock_boto3:
                mock_runtime = Mock()
                mock_bedrock_client = Mock()
                mock_boto3.client.side_effect = lambda service, region: {
                    "bedrock-runtime": mock_runtime,
                    "sts": Mock(),
                    "bedrock": mock_bedrock_client,
                }

                mock_bedrock_client.list_foundation_models.return_value = {
                    "modelSummaries": mock_bedrock_models
                }

                client = TestClient(app)

                # Setup app state
                app.state.config = mock_config
                app.state.config.admin_api_key = "test-key"
                app.state.bedrock_factory = BedrockModelFactory(mock_config)
                app.state.bedrock_client = BedrockClient()

                response = client.post(
                    "/admin/bedrock/models", headers={"x-admin-api-key": "test-key"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["models_after"] == 3

        def test_admin_endpoint_authentication(self, mock_config):
            """Test admin endpoint authentication."""
            client = TestClient(app)

            # Setup app state without admin key
            app.state.config = mock_config
            app.state.config.admin_api_key = None
            app.state.bedrock_factory = BedrockModelFactory(mock_config)

            # Test without admin key
            response = client.get("/admin/bedrock/status")
            assert response.status_code == 501

            # Test with invalid admin key
            app.state.config.admin_api_key = "test-key"
            response = client.get(
                "/admin/bedrock/status", headers={"x-admin-api-key": "wrong-key"}
            )
            assert response.status_code == 403

    class TestHarvestModelSelection:
        """Test harvest endpoint model selection."""

        @patch("src.llm_clients.boto3.client")
        def test_harvest_with_model_selection(
            self, mock_boto3, mock_config, mock_bedrock_models
        ):
            """Test harvest endpoint with model selection."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": mock_bedrock_models
            }

            # Mock successful Bedrock ask
            mock_runtime.converse.return_value = {
                "output": {"message": {"content": [{"text": "Test response"}]}}
            }

            with patch("api_server.app.state") as mock_state:
                mock_state.config = mock_config
                mock_state.bedrock_factory = BedrockModelFactory(mock_config)
                mock_state.bedrock_client = BedrockClient()
                mock_state.ocr_factory = Mock()
                mock_state.ocr_factory.get_service.return_value = Mock(available=True)

                client = TestClient(app)

                response = client.post(
                    "/harvest",
                    json={
                        "document": "data:application/pdf;base64,JVBERi0x...",
                        "question": "Test question",
                        "bedrock_model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                    },
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["model"] == "anthropic.claude-3-5-sonnet-20240620-v1:0"

        @patch("src.llm_clients.boto3.client")
        def test_harvest_invalid_model(self, mock_boto3, mock_config):
            """Test harvest endpoint with invalid model."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": mock_bedrock_models
            }

            with patch("api_server.app.state") as mock_state:
                mock_state.config = mock_config
                mock_state.bedrock_factory = BedrockModelFactory(mock_config)
                mock_state.bedrock_client = BedrockClient()
                mock_state.ocr_factory = Mock()
                mock_state.ocr_factory.get_service.return_value = Mock(available=True)

                client = TestClient(app)

                response = client.post(
                    "/harvest",
                    json={
                        "document": "data:application/pdf;base64,JVBERi0x...",
                        "question": "Test question",
                        "bedrock_model": "invalid.model.id",
                    },
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 400
                data = response.json()
                assert "invalid model" in data["detail"].lower()

    class TestModelsEndpoint:
        """Test /models endpoint includes Bedrock models."""

        @patch("src.llm_clients.boto3.client")
        def test_models_endpoint_includes_bedrock(
            self, mock_boto3, mock_config, mock_bedrock_models
        ):
            """Test /models endpoint includes Bedrock models."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.return_value = {
                "modelSummaries": mock_bedrock_models
            }

            with patch("api_server.app.state") as mock_state:
                mock_state.config = mock_config
                mock_state.bedrock_factory = BedrockModelFactory(mock_config)
                mock_state.bedrock_client = BedrockClient()

                client = TestClient(app)

                response = client.get("/models", headers={"x-api-key": "test-key"})

                assert response.status_code == 200
                data = response.json()

                model_ids = [model["id"] for model in data["data"]]
                assert "anthropic.claude-3-5-sonnet-20240620-v1:0" in model_ids
                assert "meta.llama3-1-405b-instruct-v1:0" in model_ids
                assert "amazon.titan-text-premier-v1:0" in model_ids

        @patch("src.llm_clients.boto3.client")
        def test_models_endpoint_fallback_on_error(
            self, mock_config, mock_bedrock_models
        ):
            """Test /models endpoint fallback on Bedrock error."""
            mock_runtime = Mock()
            mock_bedrock = Mock()
            mock_boto3.client.side_effect = lambda service, region: {
                "bedrock-runtime": mock_runtime,
                "sts": Mock(),
                "bedrock": mock_bedrock,
            }

            mock_bedrock.list_foundation_models.side_effect = Exception("AWS API error")

            with patch("api_server.app.state") as mock_state:
                mock_state.config = mock_config
                mock_state.bedrock_factory = BedrockModelFactory(mock_config)
                mock_state.bedrock_client = BedrockClient()

                client = TestClient(app)

                response = client.get("/models", headers={"x-api-key": "test-key"})

                assert response.status_code == 200
                data = response.json()

                # Should fallback to generic bedrock entry
                model_ids = [model["id"] for model in data["data"]]
                assert "bedrock" in model_ids


if __name__ == "__main__":
    pytest.main([__file__])
