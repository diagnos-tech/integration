"""🇺🇸 Client-side cryptography: everything clinical is encrypted here, before the network; keys stay in the enclave.

🇧🇷 Criptografia do lado do cliente: tudo que é clínico é cifrado aqui, antes da rede; as chaves ficam no enclave.
"""

from __future__ import annotations

from .encoding import b64url_decode, b64url_encode
from .entropy import EntropyMixer
from .envelope import EncryptedPayload, decrypt_content, encrypt_content, unwrap_key, wrap_key
from .hkdf import hkdf_sha256
from .hybrid import HybridKeyPair, OpenedSession, open_hybrid, seal_hybrid
from .keys import (
    DEK_INFO,
    NODE_NAME_INFO,
    RECORD_INFO,
    derive_node_key,
    derive_sse_c_key,
    generate_dek,
    sse_c_headers,
)
from .secretstream import (
    ABYTES,
    CHUNK_SIZE,
    HEADER_BYTES,
    decrypt_bytes,
    decrypt_stream,
    encrypt_bytes,
    encrypt_stream,
    encrypted_size,
)
from .secure import (
    MemoryLockWarning,
    SecretBox,
    SecretLike,
    SecureError,
    as_secret,
    harden_process,
    memory_status,
    secret_from_b64url,
    warn_if_unlocked,
    zero,
)

__all__ = [
    "ABYTES",
    "CHUNK_SIZE",
    "DEK_INFO",
    "HEADER_BYTES",
    "NODE_NAME_INFO",
    "RECORD_INFO",
    "EncryptedPayload",
    "EntropyMixer",
    "HybridKeyPair",
    "MemoryLockWarning",
    "OpenedSession",
    "SecretBox",
    "SecretLike",
    "SecureError",
    "as_secret",
    "b64url_decode",
    "b64url_encode",
    "decrypt_bytes",
    "decrypt_content",
    "decrypt_stream",
    "derive_node_key",
    "derive_sse_c_key",
    "encrypt_bytes",
    "encrypt_content",
    "encrypt_stream",
    "encrypted_size",
    "generate_dek",
    "harden_process",
    "hkdf_sha256",
    "memory_status",
    "open_hybrid",
    "seal_hybrid",
    "secret_from_b64url",
    "sse_c_headers",
    "unwrap_key",
    "warn_if_unlocked",
    "wrap_key",
    "zero",
]
