"""
config/settings.py
==================
Centralised application configuration for the Clinical Chart Extractor.
All tunable constants live here — never hard-code them in business logic.

Refocused per Production Review:
  - Primary Identity: Clinical Chart Intelligence Platform
  - Capability: AI-Powered Clinical Document Understanding
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env if present ──────────────────────────────────────────────────────
load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

# ── Gemini Configuration ──────────────────────────────────────────────────────
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
# gemini-2.0-flash: higher free-tier RPM, stable JSON output, faster than 2.5-flash
GEMINI_MODEL: str          = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Generation parameters — temperature=0 for deterministic clinical coding
# NOTE: response_mime_type intentionally omitted — it causes "E11.65." token
# injection bugs on gemini-2.5-flash. Prompt engineering handles JSON format.
GEMINI_GENERATION_CONFIG = {
    "temperature":        0.0,
    "top_p":              0.95,
    "max_output_tokens":  8192,
}

# ── PDF Parser Settings ───────────────────────────────────────────────────────
MAX_PDF_SIZE_MB: int     = 10       # Hard limit on uploaded PDF size
MIN_EXTRACTED_CHARS: int = 50       # Flag if too little text was extracted

# ── Retry Policy (tenacity) ───────────────────────────────────────────────────
RETRY_ATTEMPTS: int       = 4       # Extra attempt for 429 rate-limit recovery
RETRY_WAIT_SECONDS: float = 5.0     # Base wait — longer to survive 429 cooldowns
RETRY_MULTIPLIER: float   = 2.0
RETRY_MAX_WAIT: int       = 60      # Cap at 60s for rate-limit recovery

# ── Application Metadata ──────────────────────────────────────────────────────
APP_TITLE       = "ClinicalIQ — Clinical Chart Intelligence Platform"
APP_SUBTITLE    = "AI-Powered Clinical Document Understanding & Medical Entity Extraction"
APP_VERSION     = "1.1.0-PROD"
COMPANY_NAME    = "Clinical Natural Language Intelligence Platform"

# ── UI Constants ──────────────────────────────────────────────────────────────
SIDEBAR_WIDTH   = 340   # pixels (approximation for CSS)
SPINNER_TEXT    = "🧠  Clinical NLP Engine is analysing document structure & extracting medical entities…"
