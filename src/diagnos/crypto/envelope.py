"""The single symmetric envelope of the product: HKDF-SHA256 + AES-256-GCM.

Mirrors the vault's reference envelope byte for byte (PROTOCOL §7).
Two purposes share this mechanism, wrapping a key and encrypting a record,
but they keep separate public names and separate types on purpose: a wrapped
key goes in and comes out as a `SecretBox` (it is key material and never
touches the Python heap), while content goes in and comes out as `bytes` (it
is the caller's data, meant to be read).
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from diagnos.errors import CryptoError

from .encoding import b64url_decode, b64url_encode
from .hkdf import hkdf_sha256
from .secure import SecretBox, SecretLike, as_secret

SALT_LENGTH = 16
NONCE_LENGTH = 12
DERIVED_KEY_LENGTH = 32


@dataclass(frozen=True, slots=True)
class EncryptedPayload:
    """The `{salt, nonce, ciphertext}` shape (all b64url) that crosses the wire.

    This is the only envelope shape in the protocol. A `HybridSeal` (§6)
    reuses these same three field names even though its `salt` carries a KEM
    encapsulation instead of an HKDF salt, so the wire JSON of both looks
    identical to anything that does not know the difference.

    Attributes:
        salt: The base64url HKDF salt (or, in a `HybridSeal`, the KEM encapsulation).
        nonce: The base64url AES-GCM nonce.
        ciphertext: The base64url ciphertext followed by the GCM tag.
    """

    salt: str
    nonce: str
    ciphertext: str

    def to_dict(self) -> dict[str, str]:
        """Return the exact JSON shape the vault expects, `{salt, nonce, ciphertext}`."""
        return {"salt": self.salt, "nonce": self.nonce, "ciphertext": self.ciphertext}

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> EncryptedPayload:
        """Build a payload from a decoded JSON mapping, validating the three required fields.

        A malformed response (missing field, wrong type) is a protocol bug or
        a corrupted transport, never a signal worth distinguishing from a bad
        key at decrypt time, so it raises the same `CryptoError`.

        Args:
            mapping: The decoded JSON object holding `salt`, `nonce` and `ciphertext`.

        Returns:
            The validated payload.

        Raises:
            CryptoError: If a field is missing or is not a string.
        """
        try:
            salt, nonce, ciphertext = mapping["salt"], mapping["nonce"], mapping["ciphertext"]
        except KeyError as exc:
            raise CryptoError("EncryptedPayload: missing field (salt/nonce/ciphertext)") from exc
        if not (isinstance(salt, str) and isinstance(nonce, str) and isinstance(ciphertext, str)):
            raise CryptoError("EncryptedPayload: salt/nonce/ciphertext must be b64url strings")
        return cls(salt=salt, nonce=nonce, ciphertext=ciphertext)

    def decode(self) -> tuple[bytes, bytes, bytes]:
        """Decode the three fields to raw bytes.

        Returns:
            The `(salt, nonce, ciphertext)` triple.

        Raises:
            CryptoError: If a field is not valid base64url, like any other failure to open.
        """
        try:
            return b64url_decode(self.salt), b64url_decode(self.nonce), b64url_decode(self.ciphertext)
        except ValueError as exc:
            raise CryptoError("envelope: salt/nonce/ciphertext are not valid b64url") from exc


def _seal(wrapping_key: SecretLike, plaintext: bytes | SecretBox, info: str) -> EncryptedPayload:
    """Derive a per-call HKDF subkey, then seal with AES-256-GCM and no AAD.

    Deriving a fresh subkey per call (instead of using `wrapping_key`
    directly) means a random 16-byte salt, not nonce discipline alone, is
    what keeps two encryptions under the same wrapping key independent. It is
    cheap insurance against a nonce ever being reused.
    """
    salt = secrets.token_bytes(SALT_LENGTH)
    derived = hkdf_sha256(wrapping_key, info, DERIVED_KEY_LENGTH, salt)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    if isinstance(plaintext, SecretBox):
        ciphertext = derived.aes_gcm_seal_secret(nonce, plaintext)
    else:
        ciphertext = derived.aes_gcm_seal(nonce, plaintext)
    return EncryptedPayload(salt=b64url_encode(salt), nonce=b64url_encode(nonce), ciphertext=b64url_encode(ciphertext))


def _derived(wrapping_key: SecretLike, payload: EncryptedPayload, info: str) -> tuple[SecretBox, bytes, bytes]:
    """Return the per-payload subkey plus the raw nonce and ciphertext."""
    salt, nonce, ciphertext = payload.decode()
    return hkdf_sha256(wrapping_key, info, DERIVED_KEY_LENGTH, salt), nonce, ciphertext


def wrap_key(wrapping_key: SecretLike, key: SecretLike, info: str) -> EncryptedPayload:
    """Encrypt a key under `wrapping_key`; the key never leaves the enclave to be sealed.

    Args:
        wrapping_key: The key that protects `key`.
        key: The key material to wrap.
        info: The versioned HKDF label for this purpose (`imgexam-<purpose>-v1`).

    Returns:
        The `{salt, nonce, ciphertext}` payload to send or store.
    """
    return _seal(wrapping_key, as_secret(key), info)


def unwrap_key(wrapping_key: SecretLike, payload: EncryptedPayload, info: str) -> SecretBox:
    """Unwrap a key produced by `wrap_key`; the unwrapped key is born inside a locked box.

    Args:
        wrapping_key: The key that protects the wrapped key.
        payload: The wrapped key.
        info: The HKDF label used when wrapping.

    Returns:
        The unwrapped key in a locked `SecretBox`.

    Raises:
        CryptoError: If the payload is malformed or does not authenticate (wrong key, wrong `info`, tampering).
    """
    derived, nonce, ciphertext = _derived(wrapping_key, payload, info)
    return derived.aes_gcm_open_secret(nonce, ciphertext)


def encrypt_content(dek: SecretLike, plaintext: bytes, info: str) -> EncryptedPayload:
    """Encrypt a record (document data) under a document DEK.

    Byte for byte the same operation as `wrap_key`; see the module docstring
    for why the name still differs.

    Args:
        dek: The document's data-encryption key.
        plaintext: The record to encrypt.
        info: The versioned HKDF label for this purpose (`imgexam-<purpose>-v1`).

    Returns:
        The `{salt, nonce, ciphertext}` payload to send or store.
    """
    return _seal(dek, plaintext, info)


def decrypt_content(dek: SecretLike, payload: EncryptedPayload, info: str) -> bytes:
    """Decrypt a record produced by `encrypt_content`.

    Args:
        dek: The document's data-encryption key.
        payload: The encrypted record.
        info: The HKDF label used when encrypting.

    Returns:
        The plaintext record.

    Raises:
        CryptoError: If the payload is malformed or does not authenticate (wrong key, wrong `info`, tampering).
    """
    derived, nonce, ciphertext = _derived(dek, payload, info)
    return derived.aes_gcm_open(nonce, ciphertext)
