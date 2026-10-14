"""Level 4 of the key hierarchy: the per-version content key and the raw-byte object bodies it seals (§7).

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
"""

from __future__ import annotations

from typing import Final

from diagnos.errors import CryptoError

from .encoding import b64url_encode
from .envelope import NONCE_LENGTH, SALT_LENGTH, EncryptedPayload, decrypt_content, encrypt_content
from .hkdf import hkdf_sha256
from .secure import SecretBox, SecretLike

# Frozen wire constants (`docs/PROTOCOL.md`, "Frozen labels"); the `imgexam-` prefix is historical.
VERSION_CONTENT_INFO: Final[str] = "imgexam-document-version-v1"
DRAFT_CONTENT_INFO: Final[str] = "imgexam-document-draft-v1"

GCM_TAG_LENGTH: Final[int] = 16
# Exact difference between a sealed body and its plaintext. The signed PUT URL locks `content-length`,
# so the size is declared before sealing: `len(plaintext) + SEALED_OVERHEAD_BYTES`.
SEALED_OVERHEAD_BYTES: Final[int] = SALT_LENGTH + NONCE_LENGTH + GCM_TAG_LENGTH


def derive_content_key(dek: SecretLike, key_id: str, security_context: str) -> SecretBox:
    """Derive a per-object content key: `HKDF-SHA256(dek, salt = utf8(key_id), info = utf8(security_context))`.

    Args:
        dek: The document's data-encryption key.
        key_id: The `version_id` of a committed version, or the fixed draft key id (see `draft_key_id`).
        security_context: The opaque value the vault returns next to the signed upload or download URL.

    Returns:
        A 32-byte key, born in the enclave.
    """
    return hkdf_sha256(dek, security_context, length=32, salt=key_id.encode("utf-8"))


def seal_bytes(key: SecretLike, plaintext: bytes, info: str) -> bytes:
    """Seal `plaintext` under `key` into the raw `salt ‖ nonce ‖ ciphertext‖tag` frame.

    Args:
        key: The 32-byte content key.
        plaintext: The bytes to seal.
        info: The HKDF label of the sealing primitive (`VERSION_CONTENT_INFO` or `DRAFT_CONTENT_INFO`).

    Returns:
        The sealed body, `len(plaintext) + SEALED_OVERHEAD_BYTES` bytes long.
    """
    salt, nonce, ciphertext = encrypt_content(key, plaintext, info).decode()
    return salt + nonce + ciphertext


def open_bytes(key: SecretLike, sealed: bytes, info: str) -> bytes:
    """Open a frame produced by `seal_bytes`.

    Args:
        key: The 32-byte content key.
        sealed: The raw `salt ‖ nonce ‖ ciphertext‖tag` frame.
        info: The HKDF label the frame was sealed with.

    Returns:
        The plaintext.

    Raises:
        CryptoError: If the frame is too short to hold a salt and a nonce, or does not authenticate.
    """
    if len(sealed) <= SALT_LENGTH + NONCE_LENGTH:
        raise CryptoError("sealed body is shorter than its own framing")
    payload = EncryptedPayload(
        salt=b64url_encode(sealed[:SALT_LENGTH]),
        nonce=b64url_encode(sealed[SALT_LENGTH : SALT_LENGTH + NONCE_LENGTH]),
        ciphertext=b64url_encode(sealed[SALT_LENGTH + NONCE_LENGTH :]),
    )
    return decrypt_content(key, payload, info)


def seal_version_content(dek: SecretLike, version_id: str, security_context: str, plaintext: bytes) -> bytes:
    """Seal the body of one committed version under its own per-version key.

    Args:
        dek: The document's data-encryption key.
        version_id: The id of the version being committed; it salts the per-version key.
        security_context: The opaque value the vault returned with the signed upload URL.
        plaintext: The version's content.

    Returns:
        The sealed body, ready to `PUT` to the signed URL.
    """
    return seal_bytes(derive_content_key(dek, version_id, security_context), plaintext, VERSION_CONTENT_INFO)


def open_version_content(dek: SecretLike, version_id: str, security_context: str, sealed: bytes) -> bytes:
    """Open the body of one committed version sealed by `seal_version_content`.

    Args:
        dek: The document's data-encryption key.
        version_id: The id of the version that was sealed.
        security_context: The opaque value the vault returned with the signed download URL.
        sealed: The body as stored.

    Returns:
        The version's plaintext content.

    Raises:
        CryptoError: If the body is malformed or does not authenticate under the derived key.
    """
    return open_bytes(derive_content_key(dek, version_id, security_context), sealed, VERSION_CONTENT_INFO)


def open_draft_content(dek: SecretLike, draft_key_id: str, security_context: str, sealed: bytes) -> bytes:
    """Open a stream's draft head, which the web app autosaves.

    It uses the same scheme as committed versions, with its own `info` and a fixed key id. The draft has no
    `version_id`: it is one state per stream, overwritten in place, so its key id is fixed (`"draft"`, or
    `"draft:<stream>"` on a multi-stream resource; see `draft_key_id`).

    Args:
        dek: The document's data-encryption key.
        draft_key_id: The fixed key id of the draft, as returned by `draft_key_id()`.
        security_context: The opaque value the vault returned with the signed download URL.
        sealed: The draft body as stored.

    Returns:
        The draft's plaintext content.

    Raises:
        CryptoError: If the body is malformed or does not authenticate under the derived key.
    """
    return open_bytes(derive_content_key(dek, draft_key_id, security_context), sealed, DRAFT_CONTENT_INFO)


def draft_key_id(stream: str, *, multi_stream: bool) -> str:
    """Return the fixed key id of a stream's draft.

    Args:
        stream: The stream the draft belongs to.
        multi_stream: Whether the resource has several streams.

    Returns:
        `"draft:<stream>"` when the resource has several streams, otherwise `"draft"`.
    """
    return f"draft:{stream}" if multi_stream else "draft"
