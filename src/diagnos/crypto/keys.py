"""Key derivation glue: DEKs, `info` strings and the SSE-C sister key (PROTOCOL §7–§10).

Every `info` string below is versioned and never shared between purposes;
see `hkdf.py` for why that matters. This module is where the protocol's
purpose-to-`info` table actually lives in code, so a caller never has to
type one of these strings by hand.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Final

from .entropy import EntropyMixer
from .hkdf import hkdf_sha256
from .secure import SecretBox, SecretLike, zero

DEK_LENGTH = 32

# Every label below is a frozen wire constant: the `imgexam-` prefix predates
# the diagnos name and is baked into every ciphertext already stored, so
# renaming one would make existing documents unreadable. See
# `docs/PROTOCOL.md` ("Frozen labels"); the vectors in `tests/vectors/` pin them.
#
# `info` for wrapping a document's DEK under its security group's key. One
# label for patients, exams *and* templates: the web app seals every
# document DEK with it (`DOCUMENT_DEK_INFO` in its security module), so the
# `patient` in the name is history, not scope.
DOCUMENT_DEK_INFO: Final[str] = "imgexam-patient-dek-v1"

# `info` for sealing a document's `encrypted_index` (its list/search summary) under the document DEK.
INDEX_INFO: Final[dict[str, str]] = {
    "patients": "imgexam-patient-index-v1",
    "exams": "imgexam-exam-index-v1",
    "templates": "imgexam-template-index-v1",
}

# `info` for a drive node's own DEK, wrapped under its security group's key; there is one DEK per file or folder.
NODE_DEK_INFO: Final[str] = "imgexam-node-dek-v1"

# `info` for sealing a node's file name under the node's DEK.
NODE_NAME_INFO: Final[str] = "imgexam-node-name-v1"

# Suffix appended to `security_context` to derive the SSE-C sister key of an object's content key.
SSE_C_INFO_SUFFIX: Final[str] = "|sse-c-v1"


def generate_dek(entropy: EntropyMixer) -> SecretBox:
    """Generate a fresh 32-byte DEK, one per document or node, born inside a locked box.

    It is drawn from the mixer rather than from `os.urandom` alone so that the
    vault's per-response seed (PROTOCOL §4) reaches every DEK this process
    creates, the same composed-entropy rule the web app follows.

    Args:
        entropy: The process's entropy mixer.

    Returns:
        The new DEK in a locked `SecretBox`.
    """
    return entropy.random_secret(DEK_LENGTH)


def derive_sse_c_key(dek: SecretLike, key_id: str, security_context: str) -> bytes:
    """Derive the SSE-C customer key, the content key's sister: `HKDF(dek, salt=key_id, info=context + "|sse-c-v1")`.

    SSE-C is R2's second layer on top of the end-to-end encrypted body. This
    key goes on the wire as a header, which makes it the one derived key that
    deliberately leaves the enclave as `bytes`. It is a *sister* of the
    content key (a different `info`), so whoever learns it (R2, or anyone who
    sees the request) learns nothing about the key that protects the
    plaintext.

    Args:
        dek: The document's or node's data-encryption key.
        key_id: The `version_id` (or fixed draft key id) that salts the derivation.
        security_context: The opaque value the vault returns next to the signed URL.

    Returns:
        The 32-byte customer key.
    """
    info = security_context + SSE_C_INFO_SUFFIX
    revealed = hkdf_sha256(dek, info, length=32, salt=key_id.encode("utf-8")).reveal()
    try:
        return bytes(revealed)
    finally:
        zero(revealed)


def sse_c_headers(key: bytes) -> dict[str, str]:
    """Build the three R2/S3 SSE-C headers for `key`, as the web app sends them.

    R2 requires the customer key's MD5 as an integrity check on the header
    itself, not as a security property: MD5 here is a checksum the object
    store demands, not a cryptographic commitment to anything.

    Args:
        key: The customer key from `derive_sse_c_key`.

    Returns:
        The algorithm, key and key-MD5 headers, with the key and digest in standard padded base64.
    """
    digest = hashlib.md5(key, usedforsecurity=False).digest()
    return {
        "x-amz-server-side-encryption-customer-algorithm": "AES256",
        "x-amz-server-side-encryption-customer-key": base64.b64encode(key).decode("ascii"),
        "x-amz-server-side-encryption-customer-key-md5": base64.b64encode(digest).decode("ascii"),
    }
