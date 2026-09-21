FROM ghcr.io/astral-sh/uv:0.11.28 AS uv

FROM python:3.12-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY config ./config
COPY demo_data ./demo_data
COPY src ./src
RUN uv sync --frozen --no-dev --extra ocr --no-editable

FROM python:3.12-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TMPDIR=/tmp/screening \
    DOCTR_CACHE_DIR=/tmp/screening/doctr-cache \
    SCREENING_TEMP_ROOT=/tmp/screening
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libgl1 \
        libglib2.0-0t64 \
        libxcb1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home /app app \
    && mkdir -p /app /tmp/screening \
    && chown -R app:app /app /tmp/screening
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
USER app
EXPOSE 7860
CMD ["clinical-screening"]
