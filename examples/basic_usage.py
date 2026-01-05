#!/usr/bin/env python3
"""
Shoeshine Basic Usage Example

This example demonstrates basic usage of the Shoeshine API.

Prerequisites:
1. Start Shoeshine API: python api_server.py

Usage:
    python examples/basic_usage.py extract data/raw/doc_00000_9795.jpg
    python examples/basic_usage.py bbox data/raw/doc_00000_9795.jpg
"""

import base64
import sys
import requests


def extract_text(image_path: str) -> str:
    """Extract plain text from an image file."""
    with open(image_path, "rb") as f:
        response = requests.post(
            "http://localhost:8000/extract/text", files={"document": f}
        )

    response.raise_for_status()
    result = response.json()

    if result.get("success"):
        return result.get("text", "")
    else:
        raise RuntimeError(f"Extraction failed: {result.get('error', 'Unknown error')}")


def extract_with_bboxes(image_path: str) -> dict:
    """Extract text with bounding boxes."""
    with open(image_path, "rb") as f:
        response = requests.post(
            "http://localhost:8000/extract/bbox", files={"document": f}
        )

    response.raise_for_status()
    result = response.json()

    if result.get("success"):
        return {"text": result.get("text", ""), "items": result.get("items", [])}
    else:
        raise RuntimeError(f"Extraction failed: {result.get('error', 'Unknown error')}")


def print_usage():
    """Print usage instructions."""
    print("Shoeshine - Basic Usage Example")
    print("=" * 50)
    print("\nUsage:")
    print(f"  {sys.argv[0]} <image_path> [command]")
    print("\nCommands:")
    print("  extract    - Extract plain text from image")
    print("  bbox       - Extract text with bounding boxes")
    print("  help       - Show this help message")
    print("\nExamples:")
    print(f"  {sys.argv[0]} extract data/raw/doc_00000_9795.jpg")
    print(f"  {sys.argv[0]} bbox data/raw/doc_00000_9795.jpg")
    print("\nAPI Endpoints:")
    print("  POST /extract/text   - Extract plain text")
    print("  POST /extract/bbox   - Extract with bounding boxes")
    print("  GET  /health         - Health check")
    print("  GET  /models         - List available models")
    print("=" * 50)


def main():
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]
    image_path = sys.argv[2]

    print(f"\nShoeshine API - {command}")
    print("-" * 50)

    if command not in ["extract", "bbox", "help"]:
        print(f"\nUnknown command: {command}")
        print_usage()
        sys.exit(1)

    if command == "help":
        print_usage()
        sys.exit(0)

    # Check if file exists
    try:
        with open(image_path, "rb") as f:
            pass
    except FileNotFoundError:
        print(f"\nError: File not found: {image_path}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: Cannot read file: {e}")
        sys.exit(1)

    try:
        if command == "extract":
            text = extract_text(image_path)
            print(f"\nExtracted Text ({len(text)} characters):")
            print("-" * 50)
            print(text[:500])
            if len(text) > 500:
                print(f"... ({len(text) - 500} more characters)")
        elif command == "bbox":
            result = extract_with_bboxes(image_path)
            print(f"\nExtracted {len(result['items'])} text items with bounding boxes:")
            print("-" * 50)
            for i, item in enumerate(result["items"][:5], 1):
                print(f"  [{i}] {item['text']}")
                print(f"      Conf: {item['confidence']:.2f}, BBox: {item['bbox']}")
            if len(result["items"]) > 5:
                print(f"  ... and {len(result['items']) - 5} more items")
            print("\nFull Text:")
            print(result["text"][:300])
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
