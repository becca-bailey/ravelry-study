"""Paths, constants, and .env loading for the closing-window pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_API_DIR = DATA_DIR / "raw" / "api"
RAW_HTML_DIR = DATA_DIR / "raw" / "html"
RECON_DIR = RAW_API_DIR / "recon"
MANIFEST_DIR = DATA_DIR / "manifests"
PILOT_DIR = DATA_DIR / "pilot"
DOCS_DIR = PROJECT_ROOT / "docs"

load_dotenv(PROJECT_ROOT / ".env")

API_BASE = "https://api.ravelry.com"
REQUEST_INTERVAL_S = 1.0  # polite rate limit
MAX_RETRIES = 6


def api_credentials(scope: str = "readonly") -> tuple[str, str]:
    if scope == "personal":
        user = os.environ.get("RAVELRY_PERSONAL_USERNAME")
        password = os.environ.get("RAVELRY_PERSONAL_API_KEY")
        missing = "RAVELRY_PERSONAL_USERNAME and RAVELRY_PERSONAL_API_KEY"
    else:
        user = os.environ.get("RAVELRY_API_USERNAME")
        password = os.environ.get("RAVELRY_API_PASSWORD")
        missing = "RAVELRY_API_USERNAME and RAVELRY_API_PASSWORD"
    if not user or not password:
        raise RuntimeError(f"Set {missing} in .env (see .env.example)")
    return user, password
