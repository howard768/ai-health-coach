FROM python:3.12.13-slim-bookworm

WORKDIR /app

# Install build tools for C extensions (pycatch22, prophet cmdstanpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Pin uv; dependabot bumps via .github/dependabot.yml docker entry.
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

# Copy everything (no multi-stage caching, ensure fresh code every deploy)
COPY . .

# Install dependencies
RUN uv sync --frozen --no-dev

# Drop root for runtime. Defense-in-depth above Railway's container isolation.
# meld needs a real HOME so `uv run` has somewhere for its cache.
RUN useradd --uid 1000 --shell /usr/sbin/nologin --create-home meld \
    && chown -R meld:meld /app
USER meld

# Railway sets PORT env var
ENV PORT=8000

# Layered defense above Railway's external probe; catches local-run hangs.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/healthz', timeout=3)" || exit 1

CMD uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
