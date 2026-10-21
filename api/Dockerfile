# YomiKoe: one image that serves the API and the built web app (D21, D30; PRD "Packaging").
# Build context is the repository root:  docker compose up --build   (or)
#   docker build -f api/Dockerfile -t yomikoe .

# --- Stage 1: build the React app (web/dist) -------------------------------------------------
FROM node:24-slim AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY web/ ./
RUN npm run build

# --- Stage 2: Python runtime -------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# D15: Kokoro-82M revision; default is the pin in api/yomikoe/settings.py (DEFAULT_KOKORO_REVISION)
# and docs/PRD.md "Hugging Face models". Override with --build-arg only together with a PRD update.
ARG KOKORO_REVISION=f3ff3571791e39611d31c381e3a41a3af07b4987

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    YOMIKOE_DATA_DIR=/data \
    YOMIKOE_WEB_DIST=/app/web/dist \
    YOMIKOE_TTS_BACKEND=kokoro \
    YOMIKOE_KOKORO_REVISION=${KOKORO_REVISION} \
    HF_HOME=/hf_home

WORKDIR /app/api
COPY api/pyproject.toml api/alembic.ini ./
COPY api/yomikoe ./yomikoe

# Editable install keeps yomikoe/storage/migrations (env.py, versions/) on disk; a wheel install
# would drop them because the migrations directory is not a Python package.
# CPU-only torch from the PyTorch index keeps the image free of the CUDA wheels.
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -e ".[tts,opus]"

COPY --from=web /src/web/dist /app/web/dist

RUN mkdir -p /data /hf_home
VOLUME ["/data", "/hf_home"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/documents').status == 200 else 1)"

CMD ["python", "-m", "yomikoe", "serve", "--data-dir", "/data", "--host", "0.0.0.0", "--port", "8765"]
