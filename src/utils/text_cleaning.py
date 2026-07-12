"""Shared text-cleaning helpers for transcript processing."""

import re

BOILERPLATE_PATTERNS = [
    r"Page\s+\d+\s+of\s+\d+",
    r"^\s*Confidential\s*$",
    r"^\s*Disclaimer.*$",
    r"^\s*Transcript\s+generated\s+by.*$",
    r"^\s*www\..*$",
# TCS per-page footer - line 1 (observed 168x across 7 TCS transcripts)
    r"^Tata Consultancy Services Earnings Conference Call\s*$",
    # TCS per-page footer - line 2 with date/time + optional page marker (observed 168x)
    r"^[\d:]+\s+(?:hrs\s+)?IST\s*\(?[\d:]+\s*(?:hrs\s+)?US\s+ET\)?\s*\|\s*\d*\s*$",
    # INFY per-page header "External Document © 2025 Infosys Limited X" (observed 84x across 3 INFY transcripts)
    r"^External Document\s*©?\s*\d{4}\s+Infosys Limited\s+\d+\s*$",
    # Bare page number line (observed 25x in INFY_Q1_2023)
    r"^\s*\d{1,3}\s*$",
    # Bar page marker "| 2", "| 12" (observed 69x across 3 TCS transcripts)
    r"^\s*\|\s*\d{1,3}\s*$",
    # Edited-readability note, often with leading underscores (observed 13x)
    r".*edited for readability.*",
    # Operator script "press star then zero" - full moderator opening line (observed 18x)
    r".*press(?:ing)?\s+star\s+then\s+zero.*touchtone.*",
    # Forward-looking safe-harbor boilerplate (observed 2x)
    r".*forward[- ]looking statement.*must be reviewed in conjunction with the risks.*",
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
