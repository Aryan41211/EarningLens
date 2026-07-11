"""Shared text-cleaning helpers for transcript processing."""

import re

BOILERPLATE_PATTERNS = [
    r"Page\s+\d+\s+of\s+\d+",
    r"^\s*Confidential\s*$",
    r"^\s*Disclaimer.*$",
    r"^\s*Transcript\s+generated\s+by.*$",
    r"^\s*www\..*$",
]


def clean_extracted_text(raw_text: str) -> str:
    """Normalize extracted PDF text and remove common boilerplate lines."""
    text = raw_text.replace("[PAGE_BREAK]", "\n")

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(re.match(pat, stripped, flags=re.IGNORECASE) for pat in BOILERPLATE_PATTERNS):
            continue
        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
