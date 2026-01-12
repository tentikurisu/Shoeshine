"""Pytest configuration for Shoeshine tests."""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Set test environment (use 'local' not 'testing' which is not a valid enum)
os.environ["SHOESHINE_ENV"] = "local"
os.environ["SHOESHINE_REQUIRE_API_KEY"] = "false"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
