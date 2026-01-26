"""
LLM Clients - Bedrock Provider

Provides unified interface for LLM interactions.
This branch supports only AWS Bedrock. Ollama has been removed.
"""

import json
import logging
import os
import re
import time
import boto3
import requests
from typing import Optional, Generator, Dict, Any, List
from abc import ABC, abstractmethod

# Configure logging
logger = logging.getLogger(__name__)


def validate_model_id_format(model_id: str) -> bool:
    """Validate model ID format and prevent injection."""
    if not model_id:
        return False
    
    # Basic format validation
    if len(model_id) > 100:
        logger.warning(f"Model ID too long: {len(model_id)} chars")
        return False
    
    # Prevent injection patterns - allow only safe characters
    safe_pattern = re.compile(r'^[a-zA-Z0-9._:-]+$')
    if not safe_pattern.match(model_id):
        logger.warning(f"Invalid model ID format: {model_id}")
        return False
    
    return True


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if LLM service is available."""
        pass

    @abstractmethod
    def ask(
        self,
        text: str,
        question: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        stream: bool = False,
    ) -> str:
        """Send text and question to LLM, return answer."""
        pass

    @abstractmethod
    def stream(
        self,
        text: str,
        question: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> Generator[str, None, None]:
        """Stream LLM response as generator."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return client name."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return default model name."""
        pass


class BedrockClient(LLMClient):
    """AWS Bedrock client for document Q&A (harvest endpoint)."""

    def __init__(self, region: Optional[str] = None, model_id: Optional[str] = None):
        self.region = region or os.getenv("AWS_REGION", "eu-west-2")
        self.default_model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "")
        self.current_model_id = self.default_model_id
        self.client = boto3.client("bedrock-runtime", region_name=self.region)
        self.sts = boto3.client("sts", region_name=self.region)
        self.bedrock = boto3.client("bedrock", region_name=self.region)

    @property
    def name(self) -> str:
        return "bedrock"

    @property
    def default_model(self) -> str:
        return self.default_model_id

    def set_model(self, model_id: str) -> bool:
        """Set active model, return True if valid."""
        self.current_model_id = model_id
        return True

    def get_available_models(self, filter_active: bool = True) -> List[Dict]:
        """Get list of available Bedrock models."""
        try:
            response = self.bedrock.list_foundation_models()
            models = response.get("modelSummaries", [])
            
            if filter_active:
                models = [m for m in models if m.get("modelLifecycle", {}).get("status") == "ACTIVE"]
                models = [m for m in models if "TEXT" in m.get("inputModalities", [])]
                models = [m for m in models if "TEXT" in m.get("outputModalities", [])]
            
            return models
        except Exception as e:
            print(f"Error fetching Bedrock models: {e}")
            return []

    def validate_model(self, model_id: str) -> bool:
        """Validate model ID against available models."""
        if not model_id:
            return False
        
        # Security validation first
        if not validate_model_id_format(model_id):
            return False
        
        models = self.get_available_models()
        target_model = None
        for model in models:
            if model["modelId"] == model_id:
                target_model = model
                break
        
        if not target_model:
            return False
        
        # Validate capabilities for document Q&A
        input_modalities = target_model.get("inputModalities", [])
        output_modalities = target_model.get("outputModalities", [])
        
        # Require text input/output and streaming support
        return ("TEXT" in input_modalities and 
                "TEXT" in output_modalities and
                target_model.get("responseStreamingSupported", False))

def is_available(self) -> bool:
        """Check if AWS credentials and Bedrock access are configured."""
        try:
            self.sts.get_caller_identity()
            self.client.list_foundation_models()
            return True
        except Exception:
            return False

    def ask(
        self,
        text: str,
        question: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        stream: bool = False,
        model_id: Optional[str] = None,
    ) -> str:
        """Send text and question to Bedrock, return answer."""
        if not self.is_available():
            raise RuntimeError(
                f"Bedrock not available in region {self.region}. "
                f"Ensure AWS credentials are configured and Bedrock is enabled."
            )

        if stream:
            return self._handle_stream(text, question, system_prompt, temperature)

# Set model for this request
        if model_id:
            if not self.validate_model(model_id):
                raise ValueError(f"Invalid model ID: {model_id}")
            self.set_model(model_id)
        
        prompt = self._build_prompt(text, question, system_prompt)

        try:
            response = self.client.converse(
                modelId=self.current_model_id,
                messages=[{"role": "user", "content": prompt}],
                inferenceConfig={
                    "temperature": temperature,
                    "maxTokens": 4096,
                },
            )
            return response["output"]["message"]["content"][0]["text"]
except self.client.exceptions.AccessDeniedException as e:
            logger.error(f"Bedrock access denied: {e}")
            raise RuntimeError(f"Bedrock access denied")
        except self.client.exceptions.ValidationException as e:
            logger.error(f"Bedrock validation error: {e}")
            raise RuntimeError(f"Bedrock validation error")
        except Exception as e:
            logger.error(f"Bedrock request failed: {e}")
            raise RuntimeError(f"Bedrock request failed")

    def stream(
        self,
        text: str,
        question: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream Bedrock response chunk by chunk."""
        # Set model for this request
        if model_id:
            if not self.validate_model(model_id):
                raise ValueError(f"Invalid model ID: {model_id}")
            self.set_model(model_id)
        
        prompt = self._build_prompt(text, question, system_prompt)

        try:
            response = self.client.converse_stream(
                modelId=self.current_model_id,
                messages=[{"role": "user", "content": prompt}],
                inferenceConfig={
                    "temperature": temperature,
                    "maxTokens": 4096,
                },
            )

            for chunk in response.get("stream", []):
                if "contentBlockDelta" in chunk:
                    delta = chunk["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        yield delta["text"]
        except Exception:
            pass

    def _handle_stream(
        self,
        text: str,
        question: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        """Handle streaming response from Bedrock."""
        full_response = ""
        for chunk in self.stream(text, question, system_prompt, temperature):
            full_response += chunk
        return full_response

    def _build_prompt(
        self,
        text: str,
        question: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Build the full prompt for Bedrock."""
        default_system = (
            "You are a helpful assistant answering questions about the provided document. "
            "Base your answer ONLY on the document text provided. "
            'If the answer is not in the document, say "I don\'t have enough information."'
        )

        system = system_prompt or default_system
        return f"{system}\n\nDocument:\n{text}\n\nQuestion: {question}"


def get_llm_client(
    provider: str = "bedrock",
    region: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    """Factory function to get LLM client."""
    if provider == "bedrock":
        return BedrockClient(region=region, model_id=model)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            "Only 'bedrock' is available in the aws-bedrock-only branch."
        )


def is_llm_available(provider: str = "bedrock") -> bool:
    """Check if LLM service is available."""
    client = get_llm_client(provider)
    return client.is_available()


if __name__ == "__main__":
    client = BedrockClient()
    if client.is_available():
        print(f"Bedrock available in {client.region}")
        print(f"Model: {client.default_model_id}")
    else:
        print(f"Bedrock not available in {client.region}")
        print("Configure AWS credentials with: aws configure")
