"""Type stubs for `diagnos._secure`, the native memory enclave (Rust, `apps/sdk/native/`).

Only `diagnos.crypto` and `diagnos.session` import this module; application
code never should. Every secret here is a `SecretBox` — bytes that live in
page-locked memory and never come back as `bytes`. The full contract, threat
model and the reasons behind each method are in `apps/sdk/native/README.md`.
"""

from __future__ import annotations

from typing import Any, Final

_Buffer = bytes | bytearray | memoryview

__version__: Final[str]
SECRETSTREAM_HEADER_BYTES: Final[int]
SECRETSTREAM_ABYTES: Final[int]
X25519_PUBLIC_BYTES: Final[int]
X25519_SECRET_BYTES: Final[int]
MLKEM768_PUBLIC_BYTES: Final[int]
MLKEM768_SECRET_BYTES: Final[int]
MLKEM768_CIPHERTEXT_BYTES: Final[int]

class SecureError(Exception):
    """Any failure inside the enclave."""

class SecretBox:
    """Bytes in locked memory; no `bytes()` way out except `reveal()`."""

    @staticmethod
    def random(length: int) -> SecretBox:
        """Create a box of `length` bytes drawn from the OS random source."""
    @staticmethod
    def from_bytes(data: _Buffer) -> SecretBox:
        """Move `data` into a new locked box; a writable source is zeroed by the move."""
    def __len__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    @property
    def is_locked(self) -> bool:
        """Whether the OS accepted the `mlock` for this box (otherwise it may reach swap)."""
    @property
    def is_wiped(self) -> bool:
        """Whether `wipe()` already ran."""
    def wipe(self) -> None:
        """Zero the contents now; every later use of the box fails."""
    def clone(self) -> SecretBox:
        """Copy the contents into a second locked box."""
    def reveal(self) -> bytearray:
        """Copy the contents out as a `bytearray`; the caller must zero it. The only exit from the enclave."""
    def hmac_sha512(self, message: _Buffer) -> bytes:
        """Compute HMAC-SHA512 of `message` keyed with the box."""
    def hkdf_sha256(self, *, info: _Buffer, length: int = 32, salt: _Buffer | None = None) -> SecretBox:
        """Derive `length` bytes with HKDF-SHA256 into a new box, using this box as the input key material."""
    def aes_gcm_seal(self, nonce: _Buffer, plaintext: _Buffer, aad: _Buffer | None = None) -> bytes:
        """Encrypt `plaintext` with AES-256-GCM under this box; returns ciphertext followed by the tag."""
    def aes_gcm_seal_secret(self, nonce: _Buffer, secret: SecretBox, aad: _Buffer | None = None) -> bytes:
        """Encrypt another box's contents with AES-256-GCM under this box, without exposing them to Python."""
    def aes_gcm_open(self, nonce: _Buffer, ciphertext: _Buffer, aad: _Buffer | None = None) -> bytes:
        """Decrypt AES-256-GCM `ciphertext` (with its tag) under this box; raises `SecureError` on failure."""
    def aes_gcm_open_secret(self, nonce: _Buffer, ciphertext: _Buffer, aad: _Buffer | None = None) -> SecretBox:
        """Decrypt AES-256-GCM `ciphertext` straight into a new locked box; raises `SecureError` on failure."""
    def aes_gcm_open_json_field(
        self, nonce: _Buffer, ciphertext: _Buffer, aad: _Buffer | None, field: str
    ) -> SecretBox:
        """Decrypt a JSON object and move its base64url `field` into a new locked box, all inside the enclave."""

class HybridKeyPair:
    """X25519 + ML-KEM-768 identity, private halves locked."""

    @staticmethod
    def generate() -> HybridKeyPair: ...
    @staticmethod
    def from_secrets(x25519_secret: SecretBox, mlkem768_secret: SecretBox) -> HybridKeyPair: ...
    @property
    def x25519_public(self) -> bytes: ...
    @property
    def mlkem768_public(self) -> bytes: ...
    @property
    def is_wiped(self) -> bool: ...
    def x25519_secret(self) -> SecretBox: ...
    def mlkem768_secret(self) -> SecretBox: ...
    def open(self, encapsulation: _Buffer, nonce: _Buffer, ciphertext: _Buffer, aad: _Buffer) -> bytes: ...
    def open_secret(self, encapsulation: _Buffer, nonce: _Buffer, ciphertext: _Buffer, aad: _Buffer) -> SecretBox: ...
    def open_session(
        self, encapsulation: _Buffer, nonce: _Buffer, ciphertext: _Buffer, aad: _Buffer
    ) -> tuple[str, int, SecretBox, SecretBox]: ...
    def wipe(self) -> None: ...

class SecretStreamPush:
    """libsodium secretstream, encrypting side."""

    def __init__(self, key: SecretBox) -> None: ...
    @property
    def header(self) -> bytes: ...
    @property
    def is_finished(self) -> bool: ...
    def push(self, message: _Buffer, *, final: bool = False, ad: _Buffer | None = None) -> bytes: ...

class SecretStreamPull:
    """libsodium secretstream, decrypting side."""

    def __init__(self, key: SecretBox, header: _Buffer) -> None: ...
    @property
    def is_finished(self) -> bool: ...
    def pull(self, chunk: _Buffer, *, ad: _Buffer | None = None) -> tuple[bytes, bool]: ...

class EntropyPool:
    """OS randomness mixed with the vault's session seed."""

    def __init__(self) -> None: ...
    def mix(self, seed: SecretBox | _Buffer) -> None: ...
    def random(self, n: int) -> bytes: ...
    def random_secret(self, n: int) -> SecretBox: ...

def seal_hybrid(
    x25519_public: _Buffer, mlkem768_public: _Buffer, plaintext: _Buffer, aad: _Buffer
) -> tuple[bytes, bytes, bytes]: ...
def harden_process() -> dict[str, Any]: ...
def memory_status() -> dict[str, Any]: ...
