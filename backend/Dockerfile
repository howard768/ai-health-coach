FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY app/ app/

# Install dependencies
RUN uv sync --frozen --no-dev

# Railway sets PORT env var — default 8000 for local
ENV PORT=8000

# Shell form so $PORT gets expanded at runtime
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
