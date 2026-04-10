FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy everything (no multi-stage caching — ensure fresh code every deploy)
COPY . .

# Install dependencies
RUN uv sync --frozen --no-dev

# Railway sets PORT env var
ENV PORT=8000

CMD uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
