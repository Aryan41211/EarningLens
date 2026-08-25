# EarningsLens dashboard image.
#
# Serves the Phase 4 Streamlit dashboard over an existing scores database.
# It does NOT score: scoring needs LLM_API_KEY and burns provider quota, and
# baking a key into an image that gets pushed anywhere is how keys leak. Run
# sweeps on the host with scripts/run_all_scoring.py, then serve the result.
#
# Build:  docker build -t earningslens .
# Run:    docker run --rm -p 8501:8501 -v "$PWD/data:/app/data" earningslens
#
# The volume mount is the supported path -- the database is gitignored and
# rebuilt by scoring, so it is data, not part of the image. Without it the
# dashboard starts and says it has no scores, which is the honest empty state.

FROM python:3.12-slim

# Streamlit writes a config/stats dir at startup; give it a real home.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/app

WORKDIR /app

# Dependency layer first, so source edits do not reinstall the world.
COPY pyproject.toml README.md LICENSE ./
COPY src/__init__.py ./src/
RUN pip install --no-cache-dir \
        "pymupdf>=1.28.0,<2.0" \
        "pandas>=2.2.2,<3.0" \
        "python-dotenv>=1.2.1,<2.0" \
        "openai>=2.44.0,<3.0" \
        "streamlit>=1.56.0,<2.0" \
        "plotly>=6.7.0,<7.0"

COPY config.py ./
COPY .streamlit/ ./.streamlit/
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY notebooks/labels.csv ./notebooks/labels.csv
COPY data/ ./data/

# Run unprivileged. The mounted data volume must be writable by this uid --
# init_db opens the database read-write to apply schema migrations.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app

EXPOSE 8501

# PORT is honoured because most hosts (Render, Fly, Cloud Run) assign one.
ENV PORT=8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f\"http://localhost:{os.environ.get('PORT','8501')}/_stcore/health\").read()"

CMD ["sh", "-c", "streamlit run src/dashboard/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
