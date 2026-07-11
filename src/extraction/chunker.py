"""
Splits clean text into chunks for storage/scoring.
This module does ONE thing: clean text -> list of chunks. No cleaning, no DB.
"""


def chunk_text(text: str, target_words: int = 600) -> list[str]:
    """Splits on paragraph boundaries and packs paragraphs into chunks
    close to target_words, so sentences are never cut mid-way."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
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
