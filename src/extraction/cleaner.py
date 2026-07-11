"""
Cleans raw extracted PDF text: strips boilerplate, normalizes whitespace.
This module does ONE thing: raw text -> clean text. No extraction, no chunking.
"""

from src.utils.text_cleaning import clean_extracted_text


def clean_text(raw_text: str) -> str:
    return clean_extracted_text(raw_text)
