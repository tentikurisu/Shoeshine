#!/usr/bin/env python3
"""
Shoeshine + AWS Bedrock: Document Processing Example

This example demonstrates how to use Shoeshine with AWS Bedrock
for document processing and structured extraction using the harvest endpoint.

Prerequisites:
1. Start Shoeshine: python api_server.py
2. Configure AWS credentials:
   - SHOESHINE_API_KEY: Your Shoeshine API key
   - AWS_ACCESS_KEY_ID: Your AWS access key ID
   - AWS_SECRET_ACCESS_KEY: Your AWS secret access key
   - AWS_REGION: Your AWS region (e.g., us-east-1)
"""

import base64
import os
import sys
import boto3
import requests
from typing import Optional


SHOESHINE_URL = os.getenv("SHOESHINE_URL", "http://localhost:8000")
SHOESHINE_API_KEY = os.getenv("SHOESHINE_API_KEY", "")
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


def harvest_document(
    image_path: str,
    question: str = "Summarize this document",
    prompt: Optional[str] = None,
) -> dict:
    """Send document to Shoeshine harvest endpoint (extract + Bedrock Q&A)."""
    with open(image_path, "rb") as f:
        document_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "document": document_b64,
        "question": question,
        "prompt": prompt
        or "Answer questions about this document based ONLY on the text extracted.",
        "temperature": 0.0,
    }

    headers = {"Content-Type": "application/json"}
    if SHOESHINE_API_KEY:
        headers["X-API-Key"] = SHOESHINE_API_KEY

    response = requests.post(
        f"{SHOESHINE_URL}/harvest",
        json=payload,
        headers=headers,
    )

    response.raise_for_status()
    return response.json()


def harvest_from_s3(
    s3_bucket: str,
    s3_key: str,
    question: str = "Summarize this document",
    prompt: Optional[str] = None,
) -> dict:
    """Send S3 document to Shoeshine harvest endpoint."""
    payload = {
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "question": question,
        "prompt": prompt
        or "Answer questions about this document based ONLY on the text extracted.",
        "temperature": 0.0,
    }

    headers = {"Content-Type": "application/json"}
    if SHOESHINE_API_KEY:
        headers["X-API-Key"] = SHOESHINE_API_KEY

    response = requests.post(
        f"{SHOESHINE_URL}/harvest",
        json=payload,
        headers=headers,
    )

    response.raise_for_status()
    return response.json()


def process_document(
    image_path: str,
    question: str = "Summarize this document",
    prompt: Optional[str] = None,
) -> str:
    """Process document using Shoeshine harvest endpoint."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {image_path}")
    print(f"{'=' * 60}")

    print("1. Sending to Shoeshine harvest endpoint...")
    result = harvest_document(image_path, question, prompt)

    if not result.get("success"):
        raise RuntimeError(f"Harvest failed: {result.get('error', 'Unknown error')}")

    print(f"   Extracted {len(result.get('extracted_text', ''))} characters")
    print(f"2. Answer from Bedrock ({result.get('model')}):")

    print(f"{'=' * 60}")
    print("Answer:")
    print(result.get("answer", ""))

    return result.get("answer", "")


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python examples/bedrock_integration.py <document_path> [question]"
        )
        print("\nEnvironment Variables:")
        print(
            "  SHOESHINE_URL      - Shoeshine API URL (default: http://localhost:8000)"
        )
        print("  SHOESHINE_API_KEY  - Shoeshine API key (optional)")
        print(
            "  BEDROCK_MODEL      - Bedrock model ID (e.g., anthropic.claude-sonnet-4-20250507)"
        )
        print("  AWS_REGION         - AWS region (default: us-east-1)")
        print("  AWS_ACCESS_KEY_ID   - AWS access key ID")
        print("  AWS_SECRET_ACCESS_KEY - AWS secret access key")
        print("\nExample:")
        print(
            '  python examples/bedrock_integration.py document.jpg "What is the account number?"'
        )
        sys.exit(1)

    image_path = sys.argv[1]
    question = (
        " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Summarize this document"
    )

    try:
        answer = process_document(image_path, question)
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
