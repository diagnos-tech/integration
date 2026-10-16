"""🇺🇸 What the vault answers to `POST …/session`, built for real: material sealed to a token's own pair.

The session JSON and the group key are sealed with the SDK's `seal_hybrid`
to the token's X25519 + ML-KEM-768 public keys, with the AADs the
reference fixes, so whoever uses this exercises the enclave opening seals.

🇧🇷 O que o cofre responde a `POST …/session`, montado de verdade: material selado para o par do próprio token.

O JSON da sessão e a chave de grupo são selados com o `seal_hybrid` do SDK
para as chaves públicas X25519 + ML-KEM-768 do token, com os AADs que a
referência fixa, então quem usa isto exercita o enclave abrindo selos.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

from diagnos.crypto.encoding import b64url_decode, b64url_encode
from diagnos.crypto.hybrid import seal_hybrid
from diagnos.session.token_session import group_key_aad, session_aad
from diagnos.transport.service_token import DiagnosToken

GROUP_KEY = secrets.token_bytes(32)


def seal_to(token: DiagnosToken, plaintext: bytes, aad: str) -> dict[str, str]:
    """🇺🇸 A real seal to the token's pair, as the vault (session) or the browser (group key) makes it.

    🇧🇷 Um selo de verdade para o par do token, como o cofre (sessão) ou o navegador (chave de grupo) o fazem.
    """
    keys = token.public_keys
    payload = seal_hybrid(b64url_decode(keys["x25519"]), b64url_decode(keys["ml_kem_768"]), plaintext, aad)
    return {"salt": payload.salt, "nonce": payload.nonce, "ciphertext": payload.ciphertext}


def session_answer(token: DiagnosToken, *, session_id: str = "ses_1", aad_key_id: str | None = None) -> dict[str, Any]:
    """🇺🇸 `POST …/session`'s result: the sealed session and one sealed group key (`sg_1`).

    🇧🇷 O resultado de `POST …/session`: a sessão selada e uma chave de grupo selada (`sg_1`).
    """
    inner = {
        "session_id": "ses_1",
        "sign_key": b64url_encode(secrets.token_bytes(32)),
        "enc_key": b64url_encode(secrets.token_bytes(32)),
        "expires_at": 4_000_000_000,
    }
    key_id = aad_key_id or token.key_id
    return {
        "session_id": session_id,
        "expires_at": 4_000_000_000,
        "sealed_session": seal_to(token, json.dumps(inner).encode(), session_aad(token.workspace_id, key_id)),
        "sealed_group_keys": {"sg_1": seal_to(token, GROUP_KEY, group_key_aad(token.workspace_id, key_id, "sg_1"))},
    }
