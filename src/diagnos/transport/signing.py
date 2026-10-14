"""The request signature — mirrors the vault's canonical string byte for byte.

The vault reconstructs the canonical string from the raw request it received;
any byte this module normalizes differently is an invisible `401
SignatureInvalid` on the caller's side with nothing to grep for. Every
ambiguity below is resolved the way the TypeScript reference resolves it,
never left to "seems reasonable." The HMAC itself runs inside the enclave:
the `sign_key` is a `SecretBox` and never becomes Python `bytes`.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable

import httpx

from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretLike, as_secret

# 16 bytes matches the vault's own minimum (`docs/PROTOCOL.md §3`); more would
# just be a longer header for no extra uniqueness the OS RNG doesn't already give.
NONCE_BYTES = 16


def normalize_query(raw_query: str) -> str:
    """Sort the raw (still percent-encoded) `k=v` pairs by code point.

    Sorting the raw pairs *before* any decoding is the part that matters: two
    clients that emit the same parameters in a different order (routine
    across `URLSearchParams` implementations in different languages) land on
    the same canonical `QUERY` without either one needing to agree on
    insertion order.
    """
    if raw_query == "":
        return ""
    return "&".join(sorted(raw_query.split("&")))


def canonical_string(
    method: str,
    path: str,
    raw_query: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    r"""The six-field, `\n`-joined string HMAC-SHA512 is computed over.

    `path` is used exactly as it goes on the wire — percent-encoded, never
    decoded — because decoding before signing reopens the classic "path
    confusion" ambiguity (`%2F` vs `/`, hex case) between what the caller
    signed and what the server's router ends up serving. An empty body
    hashes to SHA-256 of the empty string, not a special-cased empty field,
    so "no body" and "an explicit zero-byte body" are always the same value.
    """
    body_digest = hashlib.sha256(body).hexdigest()
    return "\n".join(
        [
            method.upper(),
            path,
            normalize_query(raw_query),
            timestamp,
            nonce,
            body_digest,
        ]
    )


def sign_canonical(sign_key: SecretLike, canonical: str) -> str:
    """HMAC-SHA512 over the canonical string, UTF-8 encoded, hex digest (lowercase), computed inside the enclave."""
    return as_secret(sign_key).hmac_sha512(canonical.encode("utf-8")).hex()


def signature_headers(
    sign_key: SecretLike,
    *,
    method: str,
    url: httpx.URL,
    body: bytes,
    timestamp: int,
    nonce: str,
) -> dict[str, str]:
    """Build the three `X-Signature-*` headers for one request.

    `url.raw_path` is httpx's undecoded path+query exactly as it will be
    written to the socket — the same bytes the vault's own HTTP parser sees —
    so splitting it on the first `?` gives `PATH` and `QUERY` with no
    re-encoding step of our own to drift from the server's.
    """
    path, _, raw_query = url.raw_path.decode("ascii").partition("?")
    timestamp_text = str(timestamp)
    canonical = canonical_string(method, path, raw_query, timestamp_text, nonce, body)
    return {
        "X-Signature-Timestamp": timestamp_text,
        "X-Signature-Nonce": nonce,
        "X-Signature-Hmac": sign_canonical(sign_key, canonical),
    }


def new_nonce(random: Callable[[int], bytes] = secrets.token_bytes) -> str:
    """A fresh `(timestamp, nonce)` half: 16 random bytes, b64url.

    The vault treats `(timestamp, nonce)` as single-use (`409 ReplayDetected`
    on a byte-identical resend, `docs/PROTOCOL.md §3`), so every signed
    attempt — including retries — calls this again rather than reusing one.
    """
    return b64url_encode(random(NONCE_BYTES))
