# CODING_STANDARDS.md

## General style

- PEP 8 conventions.
- `snake_case` for functions/variables, `UPPER_SNAKE` for constants,
  `PascalCase` for classes (none exist yet in the codebase).
- Explicit imports only — no `from x import *` anywhere.
- Type annotations used sparingly (on function signatures where present) —
  not enforced by mypy/pyright (no config for either currently exists).
- Docstrings expected on modules and public functions.

## Structure rules

- **Single responsibility per module**: `src/extraction/` never touches
  storage; `src/storage/` never imports PyMuPDF; scoring never imports
  extraction internals.
- **`scripts/` orchestrates only** — no business logic; real logic lives
  under `src/`.
- **`config.py` is the only place paths/constants are defined** — no module
  should hardcode a path or duplicate a constant.
- **No `print()` in `src/`** — always use the structured logger
  (`src/utils/logging.py`).

## Logging

Dual-handler setup: file handler at DEBUG, console handler at INFO,
structured/timestamped format. Debug scripts (`scripts/_*.py`) are the only
place `print()` is acceptable, since they're not production code.

## Testing conventions

- Tests live in `tests/`, mirroring `src/` structure.
- LLM calls are always mocked in tests — no real API calls in CI.
- Descriptive test names; one behavior per test.
- CI runs `pytest tests/ -v` on every push/PR (Python 3.11, Ubuntu).

## Commit conventions

Conventional Commits style intended (`feat:`, `fix:`, `refactor:`, `test:`,
`docs:`, `chore:`). In practice, history has drifted — see
`PROJECT_MEMORY.md` for the noise this has caused (many generic "Updated
project" and repeated `fix(config):` messages). Going forward, prefer
one meaningful commit per logical change over squashed "Updated project"
commits.

## Hard constraints affecting code style

See `PROJECT_RULES.md` — e.g., exactly 5 scoring dimensions, no
LangChain/vector DB, paragraph-aware chunking must never split mid-sentence,
keyword matching restricted to Q&A chunks only.
