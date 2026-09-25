"""🇺🇸 Client-side cryptography: everything clinical is encrypted here, before the network; keys stay in the enclave.

🇧🇷 Criptografia do lado do cliente: tudo que é clínico é cifrado aqui, antes da rede; as chaves ficam no enclave.
"""

from __future__ import annotations

from .content import (
    SEALED_OVERHEAD_BYTES,
    derive_content_key,
    draft_key_id,
    open_draft_content,
    open_version_content,
    seal_version_content,
)
from .encoding import b64url_decode, b64url_encode
from .entropy import EntropyMixer
from .envelope import EncryptedPayload, decrypt_content, encrypt_content, unwrap_key, wrap_key
from .hkdf import hkdf_sha256
from .hybrid import HybridKeyPair, OpenedSession, open_hybrid, seal_hybrid
from .keys import (
    DOCUMENT_DEK_INFO,
    INDEX_INFO,
    NODE_NAME_INFO,
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
    "DOCUMENT_DEK_INFO",
    "HEADER_BYTES",
    "INDEX_INFO",
    "NODE_NAME_INFO",
    "SEALED_OVERHEAD_BYTES",
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
    "derive_content_key",
    "derive_node_key",
    "derive_sse_c_key",
    "draft_key_id",
    "encrypt_bytes",
    "encrypt_content",
    "encrypt_stream",
    "encrypted_size",
    "generate_dek",
    "harden_process",
    "hkdf_sha256",
    "memory_status",
    "open_draft_content",
    "open_hybrid",
    "open_version_content",
    "seal_hybrid",
    "seal_version_content",
    "secret_from_b64url",
    "sse_c_headers",
    "unwrap_key",
    "warn_if_unlocked",
    "wrap_key",
    "zero",
]
