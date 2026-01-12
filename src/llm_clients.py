"""
LLM Clients - Bedrock Provider

Provides unified interface for LLM interactions.
This branch supports only AWS Bedrock. Ollama has been removed.
"""

import json
import os
import boto3
import requests
from typing import Optional, Generator, Dict, Any
from abc import ABC, abstractmethod


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
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "")
        self.client = boto3.client("bedrock-runtime", region_name=self.region)
        self.sts = boto3.client("sts", region_name=self.region)

    @property
    def name(self) -> str:
        return "bedrock"

    @property
    def default_model(self) -> str:
        return self.model_id

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
    ) -> str:
        """Send text and question to Bedrock, return answer."""
        if not self.is_available():
            raise RuntimeError(
                f"Bedrock not available in region {self.region}. "
                f"Ensure AWS credentials are configured and Bedrock is enabled."
            )

        if stream:
            return self._handle_stream(text, question, system_prompt, temperature)

        prompt = self._build_prompt(text, question, system_prompt)

        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                inferenceConfig={
                    "temperature": temperature,
                    "maxTokens": 4096,
                },
            )
            return response["output"]["message"]["content"][0]["text"]
        except self.client.exceptions.AccessDeniedException as e:
            raise RuntimeError(f"Bedrock access denied: {str(e)}")
        except self.client.exceptions.ValidationException as e:
            raise RuntimeError(f"Bedrock validation error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Bedrock request failed: {str(e)}")

    def stream(
        self,
        text: str,
        question: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> Generator[str, None, None]:
        """Stream Bedrock response chunk by chunk."""
        prompt = self._build_prompt(text, question, system_prompt)

        try:
            response = self.client.converse_stream(
                modelId=self.model_id,
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
        print(f"Model: {client.model_id}")
    else:
        print(f"Bedrock not available in {client.region}")
        print("Configure AWS credentials with: aws configure")
