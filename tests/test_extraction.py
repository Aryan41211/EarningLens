"""
Basic tests for the extraction pipeline. Run with: pytest tests/
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.extraction.pdf_extractor import parse_filename_metadata
from src.extraction.cleaner import clean_text
from src.extraction.chunker import chunk_text


def test_parse_filename_metadata_valid():
    company, quarter, year = parse_filename_metadata("TCS_Q1_2025.pdf")
    assert company == "TCS"
    assert quarter == "Q1"
    assert year == 2025


def test_parse_filename_metadata_invalid():
    try:
        parse_filename_metadata("random_file.pdf")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_clean_text_strips_boilerplate():
    raw = "Page 1 of 2\nActual content here.\nConfidential\n"
    cleaned = clean_text(raw)
    assert "Page 1 of 2" not in cleaned
    assert "Confidential" not in cleaned
    assert "Actual content here." in cleaned


def test_chunk_text_respects_target_size():
    text = "\n\n".join([f"Paragraph number {i} with some words in it." for i in range(50)])
    chunks = chunk_text(text, target_words=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 70  # some tolerance since we don't split paragraphs
