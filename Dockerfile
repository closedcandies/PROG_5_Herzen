FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim as builder

WORKDIR /app/backend

COPY app/pyproject.toml app/uv.lock ./

ENV UV_COMPILE_BYTECODE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY app /app/backend
COPY static /app/static
COPY dumps /app/dumps

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.12-slim-bookworm AS runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app/backend

EXPOSE 8000

# Устанавливаем FFmpeg в runtime этапе
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/backend/.venv /app/.venv
COPY --from=builder /app/backend /app/backend
COPY --from=builder /app/static /app/static
COPY --from=builder /app/dumps /app/dumps

RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/backend/entrypoint.sh"]
