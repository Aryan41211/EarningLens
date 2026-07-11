"""
Extracts raw text from a PDF using PyMuPDF.
This module does ONE thing: PDF -> raw text. No cleaning, no chunking, no DB.
"""

import fitz  # PyMuPDF
import re
import os


def parse_filename_metadata(filename: str):
    """
    Expects: COMPANY_Q<n>_<year>.pdf
    e.g. TCS_Q1_2025.pdf -> ('TCS', 'Q1', 2025)
    """
    from config import FILENAME_PATTERN

    name = os.path.splitext(filename)[0]
    match = re.match(FILENAME_PATTERN, name)
    if not match:
        raise ValueError(
            f"Filename '{filename}' doesn't match COMPANY_Q<n>_<year>.pdf pattern."
        )
    company, quarter, year = match.groups()
    return company.upper(), quarter, int(year)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts raw text from every page, joined with a page-break marker
    so downstream cleaning can strip repeated per-page headers/footers."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n[PAGE_BREAK]\n".join(pages)
