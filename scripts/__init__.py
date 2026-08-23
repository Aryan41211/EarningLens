"""CLI entry points.

These stay thin: argument parsing and orchestration only, with all real logic in
`src/` (PROJECT_RULES.md). Each module's `main()` is exposed as a console script
in pyproject.toml, and every script remains runnable directly with
`python scripts/<name>.py` so existing documentation and habits keep working.
"""
