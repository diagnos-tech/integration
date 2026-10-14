"""HKDF-SHA256 (RFC 5869), the single key-derivation primitive of the SDK, run inside the enclave."""

from __future__ import annotations

from .secure import SecretBox, SecretLike, as_secret

DEFAULT_LENGTH = 32


def hkdf_sha256(
    ikm: SecretLike, info: bytes | str, length: int = DEFAULT_LENGTH, salt: bytes | None = None
) -> SecretBox:
    """Derive `length` bytes from `ikm` with domain separation by `info`; the result is a new locked box.

    `info` is the only thing that keeps two uses of the same input key
    material from producing the same output key. Every caller passes a
    versioned string (`imgexam-<purpose>-v1`) so that a future change of
    meaning never silently reuses a key. The `imgexam-` prefix is historical
    and frozen: these bytes are baked into every ciphertext already stored,
    so they are wire constants, not branding (`docs/PROTOCOL.md`, "Frozen
    labels").

    Args:
        ikm: The input key material.
        info: The domain-separation label. A `str` is encoded as UTF-8, matching the vault's TypeScript reference
            implementation, which does the same before calling `@noble/hashes`.
        length: The number of output bytes.
        salt: The HKDF salt. `None` is RFC 5869's "no salt" case (an all-zero salt of hash length).

    Returns:
        A new locked `SecretBox` holding the derived key.
    """
    info_bytes = info.encode("utf-8") if isinstance(info, str) else info
    return as_secret(ikm).hkdf_sha256(info=info_bytes, length=length, salt=salt)
