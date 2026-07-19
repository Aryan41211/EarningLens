import os
import sys
import sqlite3

import tiktoken

# Ensure project root is on PYTHONPATH so `import src...` works when running from scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.scoring.evasiveness import EVASIVENESS_SYSTEM_PROMPT, _build_qa_prompt

DB_PATH = "data/earningslens.db"
COMPANY = "TCS"
YEAR = 2023
QUARTER = "Q2"

def main():
    enc = tiktoken.get_encoding("o200k_base")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT chunk_text
        FROM transcripts
        WHERE company = ? AND year = ? AND quarter = ?
        ORDER BY chunk_index
        """,
        (COMPANY, YEAR, QUARTER),
    )
    rows = cur.fetchall()
    conn.close()

    chunks = [r[0] for r in rows]
    qa_prompt = _build_qa_prompt(chunks)

    system_tokens = enc.encode(EVASIVENESS_SYSTEM_PROMPT)
    user_tokens = enc.encode(qa_prompt)

    print("encoding=o200k_base")
    print(f"qa_chunk_count={len(chunks)}")
    print(f"qa_chunk_chars_total={sum(len(c) for c in chunks)}")
    print(f"system_prompt_tokens={len(system_tokens)}")
    print(f"user_prompt_tokens={len(user_tokens)}")
    print(f"total_tokens={len(system_tokens) + len(user_tokens)}")


if __name__ == "__main__":
    main()
