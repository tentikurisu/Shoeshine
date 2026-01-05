#!/usr/bin/env python3
"""
Shoeshine + Ollama: Document Processing Example

This example demonstrates how to use Shoeshine with a local LLM (Ollama)
for document processing and structured extraction.

Prerequisites:
1. Start Shoeshine API: python api_server.py
2. Start Ollama: ollama serve
3. Have models: ollama pull llama3

Usage:
    python examples/ollama_integration.py document.jpg "What is the bank name?"
"""

import base64
import sys
import os

import requests


# Configuration
SHOESHINE_URL = os.getenv("SHOESHINE_URL", "http://localhost:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
API_KEY = os.getenv("SHOESHINE_API_KEY", "")


def extract_text_from_document(image_path: str) -> str:
    """Extract text from document using Shoeshine API."""
    with open(image_path, "rb") as f:
        response = requests.post(
            f"{SHOESHINE_URL}/extract/text",
            headers={"X-API-Key": API_KEY} if API_KEY else {},
            files={"document": f},
        )

    response.raise_for_status()
    result = response.json()

    if not result.get("success"):
        raise RuntimeError(f"Extraction failed: {result.get('error', 'Unknown error')}")

    return result.get("text", "")


def ask_ollama(text: str, question: str) -> str:
    """Send extracted text to Ollama and get answer."""
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Answer based on the provided document text.",
                },
                {
                    "role": "user",
                    "content": f"Document:\n{text}\n\nQuestion: {question}",
                },
            ],
            "stream": False,
        },
        timeout=120,
    )

    response.raise_for_status()
    result = response.json()

    return result.get("message", {}).get("content", "")


def process_document(image_path: str, question: str = "Summarize this document"):
    """Extract text from document and send to Ollama."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {image_path}")
    print(f"{'=' * 60}")

    # Step 1: Extract text
    print("1. Extracting text from document...")
    text = extract_text_from_document(image_path)
    print(f"   Extracted {len(text)} characters")

    # Step 2: Send to Ollama
    print(f"2. Sending to Ollama ({OLLAMA_MODEL})...")
    answer = ask_ollama(text, question)

    print(f"{'=' * 60}")
    print(f"3. Answer:")
    print(answer)

    return answer


def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/ollama_integration.py <document_path> [question]")
        print("\nExample:")
        print(
            '  python examples/ollama_integration.py document.jpg "What is the account number?"'
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
