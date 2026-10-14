"""The vocabulary every interaction is written in: the fixed identity, header matchers, the envelope.

Two rules decide what goes into a matcher and what stays literal, and they are the whole point of a consumer-driven
contract:

1. Only what the SDK *reads* goes into a response. The vault may send more (Pact allows extra keys in a response body);
   the contract pins exactly what the SDK would break without, and nothing it merely tolerates.
2. A value is literal when the SDK branches on it (`"status": "approved"`, `"mode": "single"`, `"success": true`) and a
   matcher when only its shape matters (ids, timestamps, ciphertext). A renamed enum is a broken SDK; a different id is
   not.

Everything the provider must produce in its own terms (the workspace id, an enrollment id) travels as a provider-state
parameter and a `ProviderState` generator, so the vault's verification can substitute its real values instead of
guessing ours.
"""

from __future__ import annotations

import json
from typing import Any, cast

from pact import Pact, generate, match
from pact.match.matcher import GenericMatcher

from diagnos.crypto.secure import SecretBox
from diagnos.session.keyring import SessionKeys
from diagnos.transport.token import ServiceAccountToken

from _crypto import b64url, fixed_bytes, random_seed

CONSUMER = "diagnos-sdk"
PROVIDER = "diagnos-vault"

WORKSPACE_ID = "ws-contract"
ACCOUNT_ID = "acc-contract"
KEY_ID = "key-contract"
SESSION_ID = "sess-contract"
SECURITY_GROUP_ID = "sg-contract"
SIGN_KEY = fixed_bytes("session/sign-key")
ENC_KEY = fixed_bytes("session/enc-key")
SERVER_TIME_MS = 1_780_000_000_000

B64URL = r"^[A-Za-z0-9_-]+$"
ISO_INSTANT = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$"
HTTPS_URL = r"^https://.+$"
EXTERNAL_PREFIX = "/api/external/v1"


def _service_account_jwt() -> str:
    """An `apikey-<jwt>` the SDK can parse; the signature is never checked on this side (`docs/PROTOCOL.md §1`)."""
    header = b64url(json.dumps({"alg": "EdDSA", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {
        "sub": KEY_ID,
        "account_id": ACCOUNT_ID,
        "workspace_id": WORKSPACE_ID,
        "name": f"contract@{WORKSPACE_ID}.diagnos.health",
    }
    payload = b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    return f"apikey-{header}.{payload}.{b64url(fixed_bytes('token/signature', 64))}"


API_TOKEN = _service_account_jwt()
TOKEN = ServiceAccountToken.parse(API_TOKEN)


def session_keys() -> SessionKeys:
    """The session every signed interaction runs under — fresh boxes per call, since the SDK may wipe them."""
    return SessionKeys(
        session_id=SESSION_ID,
        sign_key=SecretBox.from_bytes(bytearray(SIGN_KEY)),
        enc_key=SecretBox.from_bytes(bytearray(ENC_KEY)),
        expires_at=9_999_999_999,
    )


# `HttpInteraction.with_headers` is typed `dict[str, str]` but, at runtime, hands each value to `with_header`, which
# takes matchers too. `Headers` names that, and `_headers` is the one cast.
Headers = dict[str, str]


def _headers(matchers: dict[str, object]) -> Headers:
    """See `Headers`."""
    return cast(Headers, matchers)


def workspace_state(name: str, **params: object) -> tuple[str, dict[str, object]]:
    """A provider state that always carries `workspace_id`, so the vault can bind the path to its own workspace."""
    return name, {"workspace_id": WORKSPACE_ID, **params}


def path(example: str, *, pattern: str, expression: str | None = None) -> GenericMatcher[str]:
    """A request path pinned by `pattern`, optionally rebuilt from provider-state values at verification time.

    `expression` uses `${name}` placeholders that the vault's state handler fills in (Pact's `ProviderState` generator).
    The regex is what keeps the consumer side honest: a type matcher on a path would accept *any* path.
    """
    generator = generate.provider_state(expression) if expression is not None else None
    return GenericMatcher("regex", value=example, regex=pattern, generator=generator)


def from_state(example: str, name: str) -> GenericMatcher[str]:
    """A body or query value the vault's state handler supplies at verification (`${name}`); any string here.

    It serves the few requests that carry an id the provider must choose: the version a conflict guard expects, the node
    a confirmation names, the folder a listing is scoped to.
    """
    return GenericMatcher("type", value=example, generator=generate.provider_state(f"${{{name}}}"))


def bearer_header() -> Headers:
    """`Authorization` on every request (`docs/PROTOCOL.md §1`) — its shape, not our fixed token."""
    return _headers(
        {
            "Authorization": match.regex(
                f"Bearer {API_TOKEN}", regex=r"^Bearer apikey-[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$"
            )
        }
    )


def signed_headers() -> Headers:
    """Bearer plus the three `X-Signature-*` headers (`docs/PROTOCOL.md §3`).

    The vault's verification re-signs each replayed request with a session it seeded itself. What this contract pins is
    that the SDK always sends all four headers, in the right shape.
    """
    return _headers(
        {
            **bearer_header(),
            "X-Signature-Timestamp": match.regex(str(SERVER_TIME_MS // 1000), regex=r"^[0-9]{10}$"),
            "X-Signature-Nonce": match.regex(b64url(fixed_bytes("nonce", 16)), regex=r"^[A-Za-z0-9_-]{22,}$"),
            "X-Signature-Hmac": match.regex("0" * 128, regex=r"^[0-9a-f]{128}$"),
        }
    )


def seed(*, label: str) -> dict[str, object]:
    """The `random_seed` a signed response carries in its envelope (`docs/PROTOCOL.md §4`), openable by the SDK."""
    return {"random_seed": encrypted(random_seed(ENC_KEY, SESSION_ID, label=label))}


def literal(value: object) -> GenericMatcher[object]:
    """Exact value, even inside a `like`/`each_like` whose type rule would otherwise cascade down to it."""
    return GenericMatcher("equality", value=value)


def ok(result: Any) -> dict[str, Any]:
    """The success envelope, reduced to what `transport/envelope.py` reads: `success` and `result`."""
    return {"success": True, "result": result}


def failure(code: str) -> dict[str, Any]:
    """The failure envelope as the SDK reads it: `success: false` and the first error's `code` (literal)."""
    return {"success": False, "errors": match.each_like({"code": literal(code), "message": match.str("…")})}


def encrypted(example: dict[str, str]) -> dict[str, object]:
    """An `EncryptedPayload` (`docs/PROTOCOL.md §7`): three b64url strings, each pinned by shape only."""
    return {key: match.regex(value, regex=B64URL) for key, value in example.items()}


def instant(example: str) -> GenericMatcher[str]:
    """An ISO 8601 instant — the SDK compares these (draft precedence), so the shape is pinned."""
    return GenericMatcher("regex", value=example, regex=ISO_INSTANT)


def declare_clock(pact: Pact) -> None:
    """`GET /time` (`docs/PROTOCOL.md §2`): a raw `{"result"}`, no envelope, no auth.

    Every test that makes a signed call declares it too, because the SDK syncs its clock before the first signature of
    each transport.
    """
    (
        pact.upon_receiving("the vault's clock, to correct request signatures for skew")
        .with_request("GET", "/time")
        .will_respond_with(200)
        .with_body({"result": match.number(SERVER_TIME_MS)}, content_type="application/json")
    )
