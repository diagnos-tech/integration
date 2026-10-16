"""🇺🇸 Tokens minted inside the tests — fixtures from fresh random bytes, never a real secret (spec §9).

🇧🇷 Tokens criados dentro dos testes — fixtures de bytes aleatórios novos, nunca um segredo de verdade (spec §9).
"""

from __future__ import annotations

import json
import secrets

from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.crypto.token_keys import encode_token
from diagnos.transport.service_token import DiagnosToken


def mint(workspace_id: str = "wsTest", *, seed: bytes | None = None, key_id: str | None = None) -> str:
    """🇺🇸 The text of a fresh token for `workspace_id`. 🇧🇷 O texto de um token novo para `workspace_id`."""
    raw = seed if seed is not None else secrets.token_bytes(32)
    return encode_token(key_id or f"svc_{secrets.token_hex(16)}", SecretBox.from_bytes(bytearray(raw)), workspace_id)


def parsed(workspace_id: str = "wsTest") -> DiagnosToken:
    """🇺🇸 A fresh token, already parsed. 🇧🇷 Um token novo, já lido."""
    return DiagnosToken.parse(mint(workspace_id), source="test")


def legacy_token(workspace_id: str = "wsLegacy") -> str:
    """🇺🇸 A syntactically valid, unsigned `apikey-<jwt>`. 🇧🇷 Um `apikey-<jwt>` sintaticamente válido, sem assinatura."""
    claims = {"sub": "key_9", "account_id": "acc_9", "workspace_id": workspace_id, "name": "bot@ws.diagnos.health"}
    return f"apikey-{b64url_encode(b'{}')}.{b64url_encode(json.dumps(claims).encode())}.{b64url_encode(b'sig')}"
