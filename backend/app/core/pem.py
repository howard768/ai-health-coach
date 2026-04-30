"""PEM key normalization and startup validation.

Both APNs and Sign-in-with-Apple ship private keys via Railway env vars
(`APNS_KEY_CONTENT`, `SIWA_KEY_CONTENT`). The same env-var-mangling failure
modes hit both:

  - CRLF line endings from a copy-paste through a Windows CLI
  - Literal ``\\n`` sequences when the env was set via JSON-style config
  - Missing trailing newline (cryptography is strict about this)
  - Surrounding whitespace from accidental indentation

The 2026-04-29 audit (scheduler_audit.md) traced six recurring Sentry
``JWSError: Unable to load PEM file. ... MalformedFraming`` issues to a
corrupt APNs PEM stuck in the cached singleton in ``app/services/apns.py``
forever after first load. Same shape was waiting in ``apple.py``.

Centralize the cleanup + validation here so both paths use the same logic
and we can add startup probes that fail the deploy on a corrupt key,
instead of waiting hours for the first scheduled job to surface it.
"""

from __future__ import annotations

import logging

from cryptography.hazmat.primitives.serialization import load_pem_private_key

logger = logging.getLogger("meld.pem")


def normalize_pem(raw: str) -> str:
    """Clean up env-var-mangled PEM contents.

    Steps:
      1. Replace literal ``\\n`` (two chars) with real newlines. Common when
         the env was set via JSON configs that escape newlines.
      2. Replace ``\\r\\n`` and bare ``\\r`` with ``\\n``. Handles
         CRLF-terminated paste from Windows clipboard or some CLI tools.
      3. Strip leading and trailing whitespace.
      4. Ensure exactly one trailing newline (the cryptography library is
         strict about the closing ``-----END ...----- \\n`` and rejects PEMs
         without it as MalformedFraming).
    """
    if not raw:
        return raw
    pem = raw.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n").strip()
    return pem + "\n"


def validate_pem_loads(pem: str, *, label: str) -> None:
    """Raise PemConfigError if cryptography refuses to load this PEM.

    The cheapest test for "is this PEM well-formed" is to actually parse it.
    Done at startup so misconfig fails the deploy fast.

    ``label`` shows up in the error message and logs (e.g. "APNs",
    "SIWA"). Don't include the PEM body in the error — the cryptography
    error already does that, and we don't want to log secrets.
    """
    try:
        load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception as e:  # cryptography raises various subclasses
        raise PemConfigError(
            f"{label} key failed to parse as PEM private key: {type(e).__name__}: {e}"
        ) from e
    logger.info("%s PEM loaded and parsed successfully", label)


class PemConfigError(RuntimeError):
    """Raised when a configured PEM is malformed.

    Caller (lifespan startup) bubbles it up so the deploy fails healthcheck
    and rolls back to the previous SUCCESS deploy, instead of silently
    crashing every scheduled job that needs a JWT signed by this key.
    """
