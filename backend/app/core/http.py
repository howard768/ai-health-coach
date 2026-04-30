"""Shared HTTP-client configuration.

The 2026-04-30 audit (MEL-43) found that every `httpx.AsyncClient()` in
`backend/app/services/` and most in `backend/app/core/` was created with no
`timeout=`. httpx defaults to a 5-second read timeout but no connect / write
/ pool budget, so a network hang on one upstream (Oura, Peloton, USDA,
OpenFoodFacts, Apple, APNs) can block scheduler workers and FastAPI request
workers indefinitely. The Railway healthcheck flagged this once already in
the 2026-04-29 incident era when a slow upstream pinned every worker.

`DEFAULT_TIMEOUT` is the floor every async HTTP client should pass. Override
at the call site only when you have a specific reason (e.g. long-running
streaming or batch operations).
"""

from __future__ import annotations

import httpx

# 5s to establish a TCP connection: anything longer means the upstream is
# either down or routing pathologically. 15s read: enough for slow APIs to
# return paginated responses; bounded so a hung connection doesn't block
# our worker. 10s write: covers POST bodies up to a few MB. 5s pool: do
# not wait long for a free connection from a saturated pool — fail fast
# and let the caller retry or report.
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
