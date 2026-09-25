"""🇺🇸 Level 4 of the key hierarchy: the per-version content key and the raw-byte object bodies it seals (§7).

A document's DEK never encrypts content directly. Each stored object — a
committed version, or a stream's draft head — gets its own key,
`HKDF-SHA256(dek, salt = utf8(key_id), info = utf8(security_context))`, where
`key_id` is the `version_id` (or the fixed draft id) and `security_context` is
the opaque value the vault returns next to the signed upload/download URL. The
context binds the key to the object's real address: holding the DEK without
going through the route (which audits and bills) does not reach the content.

Bodies are raw bytes, `salt(16) ‖ nonce(12) ‖ ciphertext‖tag`, not the JSON
`{salt, nonce, ciphertext}` envelope used for small key/index payloads: the
objects are binary and live in a bucket, where base64 would only add a third
to bandwidth and billable storage. The sealing itself is the same primitive as
`envelope.py` — HKDF subkey with a fresh salt, AES-256-GCM, no AAD — so every
byte of this module matches the web app's `sealedBytes.ts`, pinned by
`tests/vectors/document_content.json`.

🇧🇷 Nível 4 da hierarquia de chaves: a chave de conteúdo por versão e os corpos em bytes crus que ela sela (§7).

A DEK de um documento nunca cifra conteúdo direto. Cada objeto guardado —
uma versão confirmada, ou a cabeça de rascunho de um fluxo — ganha a própria
chave, `HKDF-SHA256(dek, salt = utf8(key_id), info = utf8(security_context))`,
onde `key_id` é o `version_id` (ou o id fixo do rascunho) e `security_context`
é o valor opaco que o cofre devolve junto da URL assinada de upload/download. O
contexto amarra a chave ao endereço real do objeto: ter a DEK sem passar pela
rota (que audita e cobra) não chega ao conteúdo.

Os corpos são bytes crus, `salt(16) ‖ nonce(12) ‖ ciphertext‖tag`, não o
envelope JSON `{salt, nonce, ciphertext}` usado para chaves e índices pequenos:
os objetos são binários e moram num bucket, onde base64 só somaria um terço à
banda e ao armazenamento faturável. A selagem em si é a mesma primitiva de
`envelope.py` — subchave HKDF com salt novo, AES-256-GCM, sem AAD — então todo
byte deste módulo bate com o `sealedBytes.ts` do app web, travado por
`tests/vectors/document_content.json`.
"""

from __future__ import annotations

from typing import Final

from diagnos.errors import CryptoError

from .encoding import b64url_encode
from .envelope import NONCE_LENGTH, SALT_LENGTH, EncryptedPayload, decrypt_content, encrypt_content
from .hkdf import hkdf_sha256
from .secure import SecretBox, SecretLike

# 🇺🇸 Frozen wire constants (`docs/PROTOCOL.md`, "Frozen labels") — the `imgexam-` prefix is historical.
# 🇧🇷 Constantes de fio congeladas (`docs/PROTOCOL.pt-BR.md`, "Rótulos congelados") — o prefixo é histórico.
VERSION_CONTENT_INFO: Final[str] = "imgexam-document-version-v1"
DRAFT_CONTENT_INFO: Final[str] = "imgexam-document-draft-v1"

GCM_TAG_LENGTH: Final[int] = 16
# 🇺🇸 Exact difference between a sealed body and its plaintext. The signed PUT URL locks `content-length`,
#    so the size is declared before sealing: `len(plaintext) + SEALED_OVERHEAD_BYTES`.
# 🇧🇷 Diferença exata entre um corpo selado e o texto claro. A URL de PUT assinada trava o `content-length`,
#    então o tamanho é declarado antes de selar: `len(plaintext) + SEALED_OVERHEAD_BYTES`.
SEALED_OVERHEAD_BYTES: Final[int] = SALT_LENGTH + NONCE_LENGTH + GCM_TAG_LENGTH


def derive_content_key(dek: SecretLike, key_id: str, security_context: str) -> SecretBox:
    """🇺🇸 `HKDF-SHA256(dek, salt = utf8(key_id), info = utf8(security_context))`, 32 bytes, born in the enclave.

    🇧🇷 `HKDF-SHA256(dek, salt = utf8(key_id), info = utf8(security_context))`, 32 bytes, nascida no enclave.
    """
    return hkdf_sha256(dek, security_context, length=32, salt=key_id.encode("utf-8"))


def seal_bytes(key: SecretLike, plaintext: bytes, info: str) -> bytes:
    """🇺🇸 Seals `plaintext` under `key` into the raw `salt ‖ nonce ‖ ciphertext` frame.

    🇧🇷 Sela `plaintext` sob `key` no enquadramento cru `salt ‖ nonce ‖ ciphertext`.
    """
    salt, nonce, ciphertext = encrypt_content(key, plaintext, info).decode()
    return salt + nonce + ciphertext


def open_bytes(key: SecretLike, sealed: bytes, info: str) -> bytes:
    """🇺🇸 The inverse of `seal_bytes`; a frame too short to hold salt and nonce is a `CryptoError`.

    🇧🇷 O inverso de `seal_bytes`; um enquadramento curto demais para salt e nonce é `CryptoError`.
    """
    if len(sealed) <= SALT_LENGTH + NONCE_LENGTH:
        raise CryptoError("sealed body is shorter than its own framing · corpo selado menor que o enquadramento")
    payload = EncryptedPayload(
        salt=b64url_encode(sealed[:SALT_LENGTH]),
        nonce=b64url_encode(sealed[SALT_LENGTH : SALT_LENGTH + NONCE_LENGTH]),
        ciphertext=b64url_encode(sealed[SALT_LENGTH + NONCE_LENGTH :]),
    )
    return decrypt_content(key, payload, info)


def seal_version_content(dek: SecretLike, version_id: str, security_context: str, plaintext: bytes) -> bytes:
    """🇺🇸 The body of one committed version, sealed under its own per-version key.

    🇧🇷 O corpo de uma versão confirmada, selado sob a própria chave da versão.
    """
    return seal_bytes(derive_content_key(dek, version_id, security_context), plaintext, VERSION_CONTENT_INFO)


def open_version_content(dek: SecretLike, version_id: str, security_context: str, sealed: bytes) -> bytes:
    """🇺🇸 The inverse of `seal_version_content`. 🇧🇷 O inverso de `seal_version_content`."""
    return open_bytes(derive_content_key(dek, version_id, security_context), sealed, VERSION_CONTENT_INFO)


def open_draft_content(dek: SecretLike, draft_key_id: str, security_context: str, sealed: bytes) -> bytes:
    """🇺🇸 Opens a stream's draft head, which the web app autosaves — same scheme, its own `info` and fixed key id.

    The draft has no `version_id`: it is one state per stream, overwritten in
    place, so its key id is fixed (`"draft"`, or `"draft:<stream>"` on a
    multi-stream resource — see `draft_key_id`).

    🇧🇷 Abre a cabeça de rascunho de um fluxo, que o app web salva automaticamente — mesmo esquema, `info` e id próprios.

    O rascunho não tem `version_id`: é um estado por fluxo, sobrescrito no
    lugar, então o id da chave é fixo (`"draft"`, ou `"draft:<fluxo>"` num
    recurso de vários fluxos — ver `draft_key_id`).
    """
    return open_bytes(derive_content_key(dek, draft_key_id, security_context), sealed, DRAFT_CONTENT_INFO)


def draft_key_id(stream: str, *, multi_stream: bool) -> str:
    """🇺🇸 The fixed key id of a stream's draft: `"draft:<stream>"` when the resource has several streams.

    🇧🇷 O id fixo da chave do rascunho de um fluxo: `"draft:<fluxo>"` quando o recurso tem vários fluxos.
    """
    return f"draft:{stream}" if multi_stream else "draft"
