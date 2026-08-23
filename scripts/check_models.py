"""List the models the configured API key can actually reach.

Hosted model names are not a stable dependency. `llama-3.3-70b-versatile` was
pinned in .env for weeks after Groq retired it, so every scoring run 404'd and
8 of the 11 evasiveness scores became unreproducible. Run this before pinning a
model, and again whenever scoring starts failing with a 404.

Usage:
    python scripts/check_models.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME


def main():
    if not LLM_API_KEY or not LLM_API_BASE_URL:
        print("LLM_API_KEY / LLM_API_BASE_URL not set in .env", file=sys.stderr)
        sys.exit(1)

    from openai import OpenAI

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE_URL)
    try:
        available = sorted(m.id for m in client.models.list().data)
    except Exception as e:
        print(f"Could not list models: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    configured_ok = LLM_MODEL_NAME in available
    print(f"Configured: {LLM_MODEL_NAME or '(unset)'}")
    print(f"Reachable : {'yes' if configured_ok else 'NO -- scoring will 404'}\n")

    print("Available on this key:")
    for model_id in available:
        marker = " <- configured" if model_id == LLM_MODEL_NAME else ""
        print(f"  {model_id}{marker}")

    if not configured_ok:
        print(
            "\nSet LLM_MODEL_NAME in .env to one of the above, then re-score the "
            "affected dimensions in full -- do not append to a series produced by "
            "a different model (SCORING_METHODOLOGY.md section 4).",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
