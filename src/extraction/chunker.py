"""
Splits clean text into chunks for storage/scoring.
This module does ONE thing: clean text -> list of chunks. No cleaning, no DB.
"""

import re


SPEAKER_LABEL_PATTERN = re.compile(
    r"^\s*([A-Z][A-Za-z .'-]{2,40}):?\s*$",
    re.MULTILINE
)


def _split_on_speakers(text: str) -> list[str]:
    """Fallback: split transcript on speaker-label lines (NAME:)
    when no paragraph breaks exist. Keeps each speaker turn as a 'paragraph'."""
    parts = SPEAKER_LABEL_PATTERN.split(text)
    # parts[0] is text before first label (header), then label, text, label, text...
    if len(parts) <= 1:
        return [text]
    paragraphs = []
    # Skip header (parts[0]), then pairs of (label, text)
    for i in range(1, len(parts), 2):
        label = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        turn = f"{label}:\n{body.strip()}"
        if turn.strip():
            paragraphs.append(turn)
    return paragraphs


def chunk_text(text: str, target_words: int = 600) -> list[str]:
    """Splits on paragraph boundaries and packs paragraphs into chunks
    close to target_words, so sentences are never cut mid-way.
    If no paragraph breaks exist (or only 1 giant paragraph), falls back to speaker-label splitting."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # Fallback: if we got only 1 paragraph and it's huge, the text has no real paragraph breaks
    if len(paragraphs) == 1 and len(paragraphs[0].split()) > target_words * 2:
        paragraphs = _split_on_speakers(text)

    chunks, current, current_count = [], [], 0

    for para in paragraphs:
        para_word_count = len(para.split())
        if current_count + para_word_count > target_words and current:
            chunks.append(" ".join(current))
            current, current_count = [], 0
        current.append(para)
        current_count += para_word_count

    if current:
        chunks.append(" ".join(current))

    return chunks
