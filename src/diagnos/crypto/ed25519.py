"""🇺🇸 Ed25519 (RFC 8032) over a seed held in the enclave — the service account credential's signature.

The seed is a `SecretBox`; signing runs in Rust against the locked page
(`apps/sdk/native/src/ed25519.rs`), so only the public key and signatures
ever reach Python.

🇧🇷 Ed25519 (RFC 8032) sobre uma semente guardada no enclave — a assinatura da credencial de conta de serviço.

A semente é um `SecretBox`; a assinatura roda em Rust contra a página
travada (`apps/sdk/native/src/ed25519.rs`), então só a chave pública e as
assinaturas chegam ao Python.
"""

from __future__ import annotations

from typing import Final

from diagnos import _secure

from .secure import SecretBox

SEED_BYTES: Final = _secure.ED25519_SEED_BYTES
PUBLIC_KEY_BYTES: Final = _secure.ED25519_PUBLIC_BYTES
SIGNATURE_BYTES: Final = _secure.ED25519_SIGNATURE_BYTES


def public_key(seed: SecretBox) -> bytes:
    """🇺🇸 The 32-byte public key of `seed`. 🇧🇷 A chave pública de 32 bytes de `seed`."""
    return _secure.ed25519_public_key(seed)


def sign(seed: SecretBox, message: bytes) -> bytes:
    """🇺🇸 The 64-byte deterministic signature of `message`. 🇧🇷 A assinatura determinística de 64 bytes."""
    return _secure.ed25519_sign(seed, message)
