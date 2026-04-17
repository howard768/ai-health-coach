#!/usr/bin/env bash
# Quick smoke test for the Meld autonomous-ops surface.
# Hits the public-facing endpoints and prints a one-line summary per check.
# Safe to run from any machine; no auth required.
#
# Usage: ./scripts/verify-autonomous-ops.sh

set -euo pipefail

PROD_URL="${PROD_URL:-https://zippy-forgiveness-production-0704.up.railway.app}"
WEB_URL="${WEB_URL:-https://heymeld.com}"

check() {
  local name="$1"
  local url="$2"
  local expect="$3"
  local body
  local code
  body=$(curl -sS -o /tmp/verify-body -w "%{http_code}" --max-time 10 "$url" 2>&1 || echo "000")
  code="$body"
  if [ "$code" = "200" ] && grep -q "$expect" /tmp/verify-body 2>/dev/null; then
    echo "OK   $name ($url)"
  else
    echo "FAIL $name ($url) http=$code expected=$expect"
    return 1
  fi
}

echo "Meld autonomous-ops surface check ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
echo "---"
check "backend /readyz"    "${PROD_URL}/readyz"     '"status":"ready"'
check "backend /ops/status" "${PROD_URL}/ops/status" '"scheduler_running":true'
check "website root"       "${WEB_URL}/"            "Meld"
echo "---"
echo "All checks passed."
