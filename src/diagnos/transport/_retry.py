"""Pure retry-policy math for `VaultTransport.request`: how long to wait before a `429`/`5xx` retry.

Kept separate from the request loop itself (`http.py`) because these are
pure functions over a response and an attempt count — no signing, no
session state — unlike `ReplayDetected`/`SignatureTimestampSkew`, which stay
in `http.py` since retrying them means re-signing a whole new request.
"""

from __future__ import annotations

from random import SystemRandom

import httpx

# §12: "RateLimitError (...) backoff"; 0.5/1/2 s is a middling curve that
# gives the vault a chance to drain without a caller waiting minutes.
RATE_LIMIT_BACKOFFS_SECONDS = (0.5, 1.0, 2.0)
MAX_RATE_LIMIT_RETRIES = 3
SERVER_ERROR_BACKOFF_SECONDS = 1.0
# Jitter only spreads out retries in time; `SystemRandom` (os.urandom-backed)
# costs nothing extra here and keeps this file from being "the one place that
# uses the non-cryptographic RNG" in a package whose whole point is crypto.
_jitter = SystemRandom()


def retry_after_seconds(response: httpx.Response) -> float | None:
    """Honour the vault's own `Retry-After` (seconds) over our guess."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def rate_limit_wait_seconds(response: httpx.Response, attempts: int) -> float:
    """Seconds to sleep before the next `429` retry: the vault's `Retry-After` if sent, else a jittered backoff."""
    wait_seconds = retry_after_seconds(response)
    if wait_seconds is not None:
        return wait_seconds
    backoff = RATE_LIMIT_BACKOFFS_SECONDS[min(attempts, len(RATE_LIMIT_BACKOFFS_SECONDS) - 1)]
    return backoff + _jitter.uniform(0, backoff / 2)
