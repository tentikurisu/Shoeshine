#!/usr/bin/env python3
"""
Shoeshine + AWS Bedrock: Document Processing Example

This example demonstrates how to use Shoeshine with AWS Bedrock
for document processing and structured extraction.

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


# Configuration
SHOESHINE_URL = os.getenv("SHOESHINE_URL", "http://localhost:8000")
SHOESHINE_API_KEY = os.getenv("SHOESHINE_API_KEY", "")
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "anthropic.claude-sonnet-4-20250507")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


def extract_text_from_document(image_path: str) -> str:
    """Extract text from document using Shoeshine API."""
    with open(image_path, "rb") as f:
        response = requests.post(
            f"{SHOESHINE_URL}/extract/text",
            headers={"X-API-Key": SHOESHINE_API_KEY} if SHOESHINE_API_KEY else {},
            files={"document": f},
        )

    response.raise_for_status()
    result = response.json()

    if not result.get("success"):
        raise RuntimeError(f"Extraction failed: {result.get('error', 'Unknown error')}")

    return result.get("text", "")


def ask_bedrock(text: str, question: str) -> str:
    """Send extracted text to AWS Bedrock."""
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise ValueError(
            "AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
        )

    # Create Bedrock client
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    # Construct prompt
    prompt = f"""Based on the following document text, answer the question.

Document:
{text}

Question: {question}

Answer based ONLY on the provided document text. If the information is not in the document, state that clearly."""

    # Call Bedrock
    response = bedrock.converse(
        modelId=BEDROCK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        inferenceConfig={
            "maxTokens": 4096,
            "temperature": 0.0,
        },
    )

    return response["output"]["message"]["content"][0]["text"]


def process_document(image_path: str, question: str = "Summarize this document"):
    """Extract text from document and send to Bedrock."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {image_path}")
    print(f"{'=' * 60}")

    # Step 1: Extract text
    print("1. Extracting text from document...")
    text = extract_text_from_document(image_path)
    print(f"   Extracted {len(text)} characters")

    # Step 2: Send to Bedrock
    print(f"2. Sending to Bedrock ({BEDROCK_MODEL})...")
    answer = ask_bedrock(text, question)

    print(f"{'=' * 60}")
    print("3. Answer:")
    print(answer)

    return answer


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
            "  BEDROCK_MODEL      - Bedrock model (default: anthropic.claude-sonnet-4-20250507)"
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
