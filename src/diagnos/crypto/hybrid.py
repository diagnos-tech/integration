"""HybridSeal — X25519 + ML-KEM-768 → HKDF-SHA256 → AES-256-GCM (PROTOCOL §6), private halves in the enclave.

The same construction seals the session (vault → SDK, on enrollment approval)
and the security-group DEKs (web app → SDK). Two KEMs, not one: an adversary
recording today's traffic and breaking X25519 tomorrow with a quantum
computer still has to break ML-KEM-768 too, and a flaw in ML-KEM's young
implementation still leaves X25519 standing. The shared secret only falls if
*both* primitives do. Reference: the vault's `hybridSeal`, pinned by `tests/vectors/hybrid_seal.json`.

The private halves never exist as Python objects: they are generated, stored
and used inside `diagnos._secure`, and what this module holds is a handle.
"""

from __future__ import annotations

from dataclasses import dataclass

from diagnos import _secure

from .encoding import b64url_encode
from .envelope import EncryptedPayload
from .secure import SecretBox, SecretLike, as_secret

# Frozen wire constant; the `imgexam-` prefix is historical (see `keys.py`).
HYBRID_SEAL_INFO = "imgexam-sdk-hybrid-seal-v1"
X25519_SECRET_BYTES = _secure.X25519_SECRET_BYTES
X25519_PUBLIC_BYTES = _secure.X25519_PUBLIC_BYTES
MLKEM768_PUBLIC_BYTES = _secure.MLKEM768_PUBLIC_BYTES
MLKEM768_SECRET_BYTES = _secure.MLKEM768_SECRET_BYTES
MLKEM768_CIPHERTEXT_BYTES = _secure.MLKEM768_CIPHERTEXT_BYTES


@dataclass(frozen=True, slots=True)
class OpenedSession:
    """What `sealed_session` opens to (PROTOCOL §5), with both keys already locked.

    Attributes:
        session_id: The vault's id for the session.
        expires_at: The session expiry, in Unix seconds.
        sign_key: The HMAC key that signs requests.
        enc_key: The key that opens the vault's per-session encrypted fields.
    """

    session_id: str
    expires_at: int
    sign_key: SecretBox
    enc_key: SecretBox


class HybridKeyPair:
    """An SDK identity: one X25519 keypair plus one ML-KEM-768 keypair.

    Secrets live in the enclave for the whole life of an enrollment (this
    pair opens every session and group key the SDK ever receives) and are
    wiped by `zeroize()` the moment the session ends.
    """

    __slots__ = ("_native",)

    def __init__(self, native: _secure.HybridKeyPair) -> None:
        """Wrap an enclave keypair; callers use `generate()` or `from_secrets()` instead.

        Args:
            native: The keypair held by the Rust enclave.
        """
        self._native = native

    @classmethod
    def generate(cls) -> HybridKeyPair:
        """Generate a fresh identity, used at enrollment time.

        Returns:
            A new key pair whose secrets live in the enclave.
        """
        return cls(_secure.HybridKeyPair.generate())

    @classmethod
    def from_secrets(cls, x25519_secret: SecretLike, mlkem768_secret: SecretLike) -> HybridKeyPair:
        """Rebuild a pair from persisted secrets (an OpenBao restore).

        Only the secrets are ever persisted (PROTOCOL §11). The public keys
        are recomputed inside the enclave rather than also stored, so there
        is one fewer place a stale or mismatched public key could sneak in.
        The ML-KEM-768 secret is the FIPS 203 expanded form (2400 bytes,
        `dk_pke ‖ ek ‖ H(ek) ‖ z`), the encoding every other implementation
        of the protocol produces.

        Args:
            x25519_secret: The X25519 secret key.
            mlkem768_secret: The expanded ML-KEM-768 secret key.

        Returns:
            The restored key pair.
        """
        return cls(_secure.HybridKeyPair.from_secrets(as_secret(x25519_secret), as_secret(mlkem768_secret)))

    @property
    def x25519_public(self) -> bytes:
        """The 32-byte X25519 public key."""
        return self._native.x25519_public

    @property
    def mlkem768_public(self) -> bytes:
        """The 1184-byte ML-KEM-768 encapsulation key."""
        return self._native.mlkem768_public

    @property
    def is_wiped(self) -> bool:
        """Whether `zeroize()` has already run."""
        return self._native.is_wiped

    def x25519_secret(self) -> SecretBox:
        """Return a locked copy of the X25519 secret, for `OpenBaoStore.save`."""
        return self._native.x25519_secret()

    def mlkem768_secret(self) -> SecretBox:
        """Return a locked copy of the expanded ML-KEM-768 secret, for `OpenBaoStore.save`."""
        return self._native.mlkem768_secret()

    def public_keys_b64url(self) -> dict[str, str]:
        """Return the base64url public keys in the shape `session/registry` expects in `public_keys`."""
        return {"x25519": b64url_encode(self.x25519_public), "mlkem768": b64url_encode(self.mlkem768_public)}

    def open(self, payload: EncryptedPayload, aad: str) -> bytes:
        """Open a seal to plain `bytes`. Use it for content, never for keys (use `open_secret`).

        Args:
            payload: The sealed `{salt, nonce, ciphertext}` envelope, whose `salt` carries the KEM encapsulation.
            aad: The context the seal is bound to, normally the `enrollment_id`.

        Returns:
            The plaintext.

        Raises:
            CryptoError: If the keys, `aad` or ciphertext do not match, or this pair was already zeroized.
        """
        encapsulation, nonce, ciphertext = payload.decode()
        return self._native.open(encapsulation, nonce, ciphertext, aad.encode("utf-8"))

    def open_secret(self, payload: EncryptedPayload, aad: str) -> SecretBox:
        """Open a seal straight into a locked box, as for a group DEK.

        Args:
            payload: The sealed `{salt, nonce, ciphertext}` envelope, whose `salt` carries the KEM encapsulation.
            aad: The context the seal is bound to, normally the `enrollment_id`.

        Returns:
            The plaintext in a locked `SecretBox`.

        Raises:
            CryptoError: If the keys, `aad` or ciphertext do not match, or this pair was already zeroized.
        """
        encapsulation, nonce, ciphertext = payload.decode()
        return self._native.open_secret(encapsulation, nonce, ciphertext, aad.encode("utf-8"))

    def open_session(self, payload: EncryptedPayload, aad: str) -> OpenedSession:
        """Open `sealed_session` (PROTOCOL §5); the JSON and both keys are parsed inside the enclave.

        Args:
            payload: The sealed session envelope.
            aad: The context the seal is bound to, normally the `enrollment_id`.

        Returns:
            The session id, expiry and the two session keys.

        Raises:
            CryptoError: If the keys, `aad` or ciphertext do not match, the JSON is malformed, or this pair was
                already zeroized.
        """
        encapsulation, nonce, ciphertext = payload.decode()
        session_id, expires_at, sign_key, enc_key = self._native.open_session(
            encapsulation, nonce, ciphertext, aad.encode("utf-8")
        )
        return OpenedSession(session_id=session_id, expires_at=expires_at, sign_key=sign_key, enc_key=enc_key)

    def zeroize(self) -> None:
        """Wipe both secrets now; every later `open` fails."""
        self._native.wipe()

    def __repr__(self) -> str:
        """Render the pair without revealing any secret."""
        return f"HybridKeyPair(x25519={b64url_encode(self.x25519_public)[:8]}…, mlkem768=<1184 B>, secrets=<enclave>)"


def seal_hybrid(x25519_public: bytes, mlkem768_public: bytes, plaintext: bytes, aad: str) -> EncryptedPayload:
    """Seal `plaintext` to a recipient's public keys; `aad` binds the seal to its context.

    `aad` is always the `enrollment_id`: a seal produced for one enrollment
    must not open under another, even with the same recipient keys. The SDK
    itself only *opens* seals; this function exists for tests and for tooling
    that plays the vault's or the web app's role.

    Args:
        x25519_public: The recipient's 32-byte X25519 public key.
        mlkem768_public: The recipient's ML-KEM-768 encapsulation key.
        plaintext: The bytes to seal.
        aad: The context to bind the seal to.

    Returns:
        The sealed `{salt, nonce, ciphertext}` envelope, whose `salt` carries the KEM encapsulation.
    """
    encapsulation, nonce, ciphertext = _secure.seal_hybrid(
        x25519_public, mlkem768_public, plaintext, aad.encode("utf-8")
    )
    return EncryptedPayload(
        salt=b64url_encode(encapsulation), nonce=b64url_encode(nonce), ciphertext=b64url_encode(ciphertext)
    )


def open_hybrid(keypair: HybridKeyPair, payload: EncryptedPayload, aad: str) -> bytes:
    """Open a seal with `keypair`, as a function form of `keypair.open(payload, aad)`.

    Args:
        keypair: The recipient's key pair.
        payload: The sealed envelope.
        aad: The context the seal is bound to.

    Returns:
        The plaintext.

    Raises:
        CryptoError: On a wrong `aad`, wrong keys or tampering.
    """
    return keypair.open(payload, aad)
