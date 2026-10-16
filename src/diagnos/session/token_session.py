"""🇺🇸 Opening a session with the token (spec §5): one signed request, no pairing, no human in the loop.

`POST /api/external/v1/workspaces/{workspace_id}/session` carries only the
token's hybrid signature (RFC 9421) — no session exists yet, so there is no
session HMAC. The vault answers with the session's HMAC and AES keys sealed
to the token's X25519 + ML-KEM-768 pair, plus the key of every security
group in the token's scope, sealed by the browser when the token was
created. Both open here, inside the enclave, with keys derived from the
seed. Each seal's AAD binds it to its place — workspace, key and, for a
group key, the group — so seals swapped around in the vault's database fail
to open instead of handing over the wrong key.

🇧🇷 Abrir uma sessão com o token (spec §5): uma requisição assinada, sem pareamento, sem pessoa no meio.

`POST /api/external/v1/workspaces/{workspace_id}/session` leva só a
assinatura híbrida do token (RFC 9421) — ainda não existe sessão, então não
há HMAC de sessão. O cofre responde com as chaves HMAC e AES da sessão
seladas para o par X25519 + ML-KEM-768 do token, mais a chave de todo grupo
de segurança do escopo do token, seladas pelo navegador quando o token foi
criado. As duas abrem aqui, dentro do enclave, com chaves derivadas da
semente. O AAD de cada selo o amarra ao seu lugar — workspace, chave e, na
chave de grupo, o grupo — então selos trocados de lugar no banco do cofre
deixam de abrir em vez de entregar a chave errada.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from diagnos.crypto.envelope import EncryptedPayload
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import SecretBox
from diagnos.errors import CryptoError, ProtocolError
from diagnos.session.keyring import Keyring, SessionKeys

# 🇺🇸 Type-only, like `enrollment.py`: `diagnos.transport` imports `diagnos.session.keyring` at import time.
# 🇧🇷 Só de tipo, como em `enrollment.py`: `diagnos.transport` importa `diagnos.session.keyring` no import.
if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport
    from diagnos.transport.service_token import DiagnosToken

SESSION_AAD_PREFIX: Final = "diagnos-sa-session-v1"
GROUP_KEY_AAD_PREFIX: Final = "diagnos-sa-group-kek-v1"
_GROUP_KEY_LENGTH: Final = 32


def session_path(workspace_id: str) -> str:
    """🇺🇸 The route that opens a session. 🇧🇷 A rota que abre uma sessão."""
    return f"/api/external/v1/workspaces/{workspace_id}/session"


def lock_path(workspace_id: str) -> str:
    """🇺🇸 The token's lock route; `/session/lock` without a workspace is the legacy token's.

    🇧🇷 A rota de lock do token; `/session/lock` sem workspace é a do token legado.
    """
    return f"{session_path(workspace_id)}/lock"


def session_aad(workspace_id: str, key_id: str) -> str:
    """🇺🇸 `diagnos-sa-session-v1:<workspace_id>:<key_id>`. 🇧🇷 O AAD do selo da sessão."""
    return f"{SESSION_AAD_PREFIX}:{workspace_id}:{key_id}"


def group_key_aad(workspace_id: str, key_id: str, security_group_id: str) -> str:
    """🇺🇸 `diagnos-sa-group-kek-v1:<workspace_id>:<key_id>:<group>` — the group id last, so it may hold `:`.

    🇧🇷 `diagnos-sa-group-kek-v1:<workspace_id>:<key_id>:<grupo>` — o id do grupo por último, para poder ter `:`.
    """
    return f"{GROUP_KEY_AAD_PREFIX}:{workspace_id}:{key_id}:{security_group_id}"


def _group_keys(keypair: HybridKeyPair, token: DiagnosToken, sealed: Any) -> dict[str, SecretBox]:
    """🇺🇸 Opens every group key into a locked 32-byte box; a wrong length is a protocol mismatch.

    🇧🇷 Abre toda chave de grupo numa caixa travada de 32 bytes; tamanho errado é incompatibilidade de protocolo.
    """
    opened: dict[str, SecretBox] = {}
    for security_group_id, seal in dict(sealed or {}).items():
        aad = group_key_aad(token.workspace_id, token.key_id, security_group_id)
        key = keypair.open_secret(EncryptedPayload.from_dict(seal), aad)
        if len(key) != _GROUP_KEY_LENGTH:
            key.wipe()
            for other in opened.values():
                other.wipe()
            raise CryptoError(
                f"🇺🇸 the key of group {security_group_id!r} opened to {len(key)} bytes, expected "
                f"{_GROUP_KEY_LENGTH}. 🇧🇷 a chave do grupo {security_group_id!r} abriu com {len(key)} bytes, "
                f"esperado {_GROUP_KEY_LENGTH}."
            )
        opened[security_group_id] = key
    return opened


def open_token_session(transport: VaultTransport, token: DiagnosToken, keypair: HybridKeyPair) -> Keyring:
    """🇺🇸 Ask the vault for a session and open what it sealed; `keypair` is the token's (`token.keypair()`).

    `signed=False`: there is no session HMAC before the session exists. The
    token's own signature, on every request, is what authenticates this one.
    The session id and expiry are read from inside the seal — the copies
    beside it are only for scheduling — and must agree with them.

    🇧🇷 Pede uma sessão ao cofre e abre o que ele selou; `keypair` é o do token (`token.keypair()`).

    `signed=False`: não há HMAC de sessão antes de a sessão existir. A própria
    assinatura do token, em toda requisição, é o que autentica esta. O id e a
    validade da sessão são lidos de dentro do selo — as cópias ao lado servem
    só para agendar — e precisam concordar com eles.
    """
    result = transport.post(session_path(token.workspace_id), signed=False)
    payload = EncryptedPayload.from_dict(result["sealed_session"])
    opened = keypair.open_session(payload, session_aad(token.workspace_id, token.key_id))
    if result.get("session_id", opened.session_id) != opened.session_id:
        opened.sign_key.wipe()
        opened.enc_key.wipe()
        raise ProtocolError(
            "🇺🇸 the vault's session id disagrees with the sealed one. 🇧🇷 o id de sessão do cofre discorda do selado."
        )
    session = SessionKeys(
        session_id=opened.session_id, sign_key=opened.sign_key, enc_key=opened.enc_key, expires_at=opened.expires_at
    )
    try:
        group_keys = _group_keys(keypair, token, result.get("sealed_group_keys"))
    except Exception:
        session.zeroize()
        raise
    return Keyring(enrollment_id=opened.session_id, session=session, group_keys=group_keys)
