#!/usr/bin/env python3
"""
Test script to verify Shoeshine API and Ollama connectivity
"""

import subprocess
import time
import sys
import requests
import os


def wait_for_url(url, timeout=30):
    """Wait for URL to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.5)
    return False


def main():
    print("=" * 60)
    print("Shoeshine + Ollama Test")
    print("=" * 60)

    # Test Ollama
    print("\n1. Testing Ollama...")
    try:
        resp = requests.get("http://localhost:11434/api/version", timeout=5)
        print(f"   Ollama version: {resp.json().get('version', 'unknown')}")

        models = requests.get("http://localhost:11434/api/tags", timeout=5)
        model_list = [m["name"] for m in models.json().get("models", [])]
        print(f"   Models: {', '.join(model_list)}")

        if "llama3" in " ".join(model_list):
            print("   ✓ llama3 available")
        else:
            print("   ✗ llama3 NOT available. Run: ollama pull llama3")
    except Exception as e:
        print(f"   ✗ Ollama not accessible: {e}")
        print("   Start with: ollama serve")
        return

    # Test Shoeshine
    print("\n2. Testing Shoeshine...")
    try:
        resp = requests.get("http://localhost:8000/health", timeout=5)
        data = resp.json()
        print(f"   Status: {data.get('status')}")
        print(f"   OCR: {data.get('services', {}).get('ocr')}")
    except Exception as e:
        print(f"   ✗ Shoeshine not accessible: {e}")
        print("   Start with: python api_server.py")
        return

    print("\n" + "=" * 60)
    print("Both services are running!")
    print("=" * 60)
    print("\nTry the API at: http://localhost:8000/docs")
    print("Or use the CLI: python ask_doc.py document.pdf 'What is this?'")


if __name__ == "__main__":
    main()
