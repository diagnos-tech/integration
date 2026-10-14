"""The bridge to `diagnos._secure`, the Rust memory enclave every secret in this SDK lives in.

A `SecretBox` is bytes in page-locked memory (`mlock`), fenced by guard
pages, excluded from core dumps, wiped in a `fork()` child and zeroed the
moment the box is dropped. It never comes back as `bytes`: HMAC, HKDF,
AES-GCM, the hybrid seal and the secretstream all run inside the enclave,
against the locked page. The single exit is `SecretBox.reveal()`, reserved
for the OpenBao export (`session/unseal.py`), and every caller of it zeroes
the `bytearray` it gets. `apps/sdk/native/README.md` has the threat model.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

from diagnos import _secure

from .encoding import b64url_decode

SecretBox = _secure.SecretBox
SecureError = _secure.SecureError

# What a key parameter accepts: a box, or bytes-like material that will be
# moved into one (a writable source is zeroed by the move).
SecretLike = SecretBox | bytes | bytearray | memoryview

logger = logging.getLogger("diagnos")
_warned_unlocked = False


class MemoryLockWarning(RuntimeWarning):
    """Emitted once when the OS refused to lock at least one secret in RAM.

    The secret still has guard pages, no-dump and zero-on-drop; what it lost
    is the guarantee of never reaching swap. The fix is operational, not in
    code: raise `ulimit -l`, grant `CAP_IPC_LOCK`, or set
    `DIAGNOS_MEMORY_LOCK=require` to refuse to run this way.
    """


def as_secret(value: SecretLike) -> SecretBox:
    """Return a `SecretBox` for `value`: the box itself, or a fresh one holding a copy of the bytes.

    Copying `bytes` in cannot erase the caller's original, because `bytes` is
    immutable. The only paths that pass `bytes` here are test vectors and the
    OpenBao restore, both documented as such. Writable sources (`bytearray`,
    writable `memoryview`) are zeroed by the move.

    Args:
        value: An existing box, or bytes-like key material.

    Returns:
        `value` itself if it is already a box, otherwise a new locked box.
    """
    if isinstance(value, SecretBox):
        return value
    return SecretBox.from_bytes(value)


def secret_from_b64url(text: str) -> SecretBox:
    """Decode base64url straight into a box.

    `base64` returns immutable `bytes`, so one transient clear copy exists
    on the Python heap until the collector frees it. That is why this helper
    is used only on the OpenBao restore path, never for material the vault
    sends (that is opened inside the enclave; see `transport/seed.py`).

    Args:
        text: The base64url text, with or without padding.

    Returns:
        The decoded bytes in a locked box.
    """
    return SecretBox.from_bytes(bytearray(b64url_decode(text)))


def zero(buffer: bytearray) -> None:
    """Overwrite a `bytearray` (typically from `reveal()`) with zeros, in place."""
    buffer[:] = bytes(len(buffer))


def memory_status() -> dict[str, Any]:
    """Report what the enclave guarantees right now (lock policy, unlocked allocations, limits)."""
    return dict(_secure.memory_status())


def harden_process() -> dict[str, Any]:
    """Disable core dumps and `ptrace` attach for this process and raise the memlock soft limit; idempotent."""
    return dict(_secure.harden_process())


def warn_if_unlocked() -> None:
    """Emit `MemoryLockWarning` (once per process) if any secret could not be locked.

    It is called right after a session is unlocked, the moment the process
    holds every secret it will ever hold, so the warning reflects the real
    footprint and not an early, optimistic zero.
    """
    global _warned_unlocked  # noqa: PLW0603 — one warning per process is the whole point
    status = memory_status()
    if _warned_unlocked or int(status.get("unlocked_allocations", 0)) == 0:
        return
    _warned_unlocked = True
    warnings.warn(
        "diagnos could not lock every secret in RAM (mlock refused, errno "
        f"{status.get('last_lock_errno')}); keys may reach swap. Raise `ulimit -l`, grant CAP_IPC_LOCK, "
        "or set DIAGNOS_MEMORY_LOCK=require to refuse to run this way.",
        MemoryLockWarning,
        stacklevel=2,
    )
    logger.warning("secure memory: %s", status)
