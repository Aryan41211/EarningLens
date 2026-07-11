"""
EarningsLens - Central Configuration

Every path and constant used across the project lives here.
No module in src/ should hardcode a path - import from config instead.
"""

import os
from pathlib import Path

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

# Common company tickers and quarter values used throughout the project.
COMPANIES = [
    "TCS",
    "INFY",
    "WIPRO",
    "HDFCBANK",
]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# ---------- Chunking ----------
CHUNK_TARGET_WORDS = 600

# ---------- LLM API (used starting Phase 2 - not needed for Phase 1) ----------
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE_URL = os.environ.get("LLM_API_BASE_URL", "")  # OpenAI-compatible endpoint
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "")

# ---------- Scoring dimensions (Phase 2 reference - not implemented yet) ----------
SCORE_DIMENSIONS = [
    "evasiveness",
    "sentiment_shift",
    "complexity_spike",
    "overpromising",
    "forward_guidance_vagueness",
]
