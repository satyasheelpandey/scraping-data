"""
Pytest configuration and fixtures for scraping-data tests.
"""
import sys
import os
from pathlib import Path
from unittest.mock import patch

# Add Scraping_code to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "Scraping_code"))

# Mock environment variables to avoid .env dependency
os.environ['OPENAI_API_KEY'] = 'test-api-key-for-testing'
os.environ['GOOGLE_API_KEY'] = 'test-google-key'
os.environ['GOOGLE_CSE_ID'] = 'test-cse-id'
os.environ['GOOGLE_DEAL_API_KEY'] = 'test-deal-api-key'
os.environ['GOOGLE_DEAL_CX'] = 'test-deal-cx-id'
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'
