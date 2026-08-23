"""
EarningsLens - Central Configuration

Every path and constant used across the project lives here.
No module in src/ should hardcode a path - import from config instead.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------- Paths ----------
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
PROCESSED_DIR = DATA_DIR / "processed"
FINDINGS_DIR = DATA_DIR / "findings"
DB_PATH = DATA_DIR / "earningslens.db"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

# ---------- Filename convention ----------
# Expected PDF filename pattern: COMPANY_Q<n>_<year>.pdf  e.g. TCS_Q1_2025.pdf
FILENAME_PATTERN = r"^([A-Za-z0-9&]+)_(Q[1-4])_(\d{4})$"

# NOTE: COMPANIES and QUARTERS were removed here. Neither was read anywhere in
# src/, scripts/, or tests/, and COMPANIES listed two companies (WIPRO,
# HDFCBANK) that have never been ingested -- so the "supported companies" list
# was a claim nothing enforced and nothing honoured. Ingestion accepts any
# ticker matching FILENAME_PATTERN, and the valid quarters are already encoded
# in that regex. Add a real watchlist here only if something validates against it.

# ---------- Logging ----------
LOG_PATH = DATA_DIR / "earningslens.log"

# ---------- PDF Validation ----------
MIN_EXTRACTED_WORDS = 50  # reject suspiciously small extractions

# ---------- Chunking ----------
CHUNK_TARGET_WORDS = 600

# ---------- LLM API (used starting Phase 2 - not needed for Phase 1) ----------
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE_URL = os.environ.get("LLM_API_BASE_URL", "")  # OpenAI-compatible endpoint
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "")

# ---------- Scoring dimensions (Phase 2) ----------
SCORE_DIMENSIONS = [
    "evasiveness",
    "sentiment_shift",
    "complexity_spike",
    "overpromising",
    "forward_guidance_vagueness",
]
