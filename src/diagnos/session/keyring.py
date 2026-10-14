"""In-memory secrets a live enrollment holds: session keys and group DEKs, every one a `SecretBox`.

Nothing here is `bytes` or `bytearray`: each key is a `SecretBox`, bytes in
page-locked Rust memory (`crypto/secure.py`) that never come back to the
Python heap. Signing, opening a seed and unwrapping a document key all happen
inside the enclave. `zeroize()` wipes each box the moment the session ends
instead of hoping for a timely garbage collection. Nothing in this module
ever touches the network or the filesystem, which is the whole point of a
keyring: it is the one place in the SDK that the vault's own protocol does
not reach.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from diagnos.crypto.secure import SecretBox
from diagnos.errors import DiagnosError

DEFAULT_VALIDITY_MARGIN_SECONDS = 60


class GroupKeyUnavailable(DiagnosError):  # noqa: N818 — a missing DEK is a permission gap, not an "Error"
    """The SDK was never handed the DEK of this security group.

    This happens when an admin approves an enrollment for a narrower set of
    groups than the document being opened needs. It is a permissions gap, not
    a crypto failure, so it is its own exception rather than `CryptoError`.
    """


@dataclass
class SessionKeys:
    """The symmetric keys of one enrollment session (`docs/PROTOCOL.md §4`).

    Attributes:
        session_id: The vault's id for the session.
        sign_key: The HMAC key that signs requests.
        enc_key: The key that opens the vault's per-response encrypted fields.
        expires_at: The session expiry, in Unix seconds.
    """

    session_id: str
    sign_key: SecretBox
    enc_key: SecretBox
    expires_at: int

    def is_valid(self, now: int | None = None, margin_seconds: int = DEFAULT_VALIDITY_MARGIN_SECONDS) -> bool:
        """Return `True` while more than `margin_seconds` remain before `expires_at`.

        The margin exists so that a request does not start signing with a
        session that expires mid-flight. A request accepted at `t` but checked
        by the vault at `t + network latency` should not depend on that race.

        Args:
            now: The current time in Unix seconds; defaults to the system clock.
            margin_seconds: How far ahead of `expires_at` the session stops counting as valid.

        Returns:
            Whether the session is still safe to sign with.
        """
        current = now if now is not None else int(time.time())
        return current + margin_seconds < self.expires_at

    def zeroize(self) -> None:
        """Wipe both keys; call this the moment the session ends."""
        self.sign_key.wipe()
        self.enc_key.wipe()

    def __repr__(self) -> str:
        """Render the session without its keys, because this is what ends up in a log line."""
        return (
            f"SessionKeys(session_id={self.session_id!r}, expires_at={self.expires_at!r}, "
            f"sign_key=<redacted {len(self.sign_key)}B>, enc_key=<redacted {len(self.enc_key)}B>)"
        )


@dataclass
class Keyring:
    """One enrollment's full unlocked state: its session plus its group DEKs.

    Attributes:
        enrollment_id: The id of the approved enrollment.
        session: The session keys.
        group_keys: The DEK of each security group the enrollment may use, keyed by group id.
    """

    enrollment_id: str
    session: SessionKeys
    group_keys: dict[str, SecretBox] = field(default_factory=dict)

    def group_key(self, security_group_id: str) -> SecretBox:
        """Return the locked 32-byte DEK of `security_group_id`.

        The box itself is returned, not a copy: a `SecretBox` cannot be read
        or mutated by accident, only used inside the enclave or wiped on
        purpose, so there is nothing a caller could do to it that a copy
        would need to protect against, and it saves one locked page per call.

        Args:
            security_group_id: The security group whose DEK is wanted.

        Returns:
            The group's DEK.

        Raises:
            GroupKeyUnavailable: If the enrollment was not handed a DEK for that group.
        """
        key = self.group_keys.get(security_group_id)
        if key is None:
            raise GroupKeyUnavailable(
                f"no DEK for security group {security_group_id!r} was handed to this "
                "enrollment — ask a workspace admin to include it in the next approval."
            )
        return key

    @property
    def security_group_ids(self) -> list[str]:
        """The ids of every group this enrollment holds a DEK for."""
        return list(self.group_keys.keys())

    def zeroize(self) -> None:
        """Wipe the session keys and every group DEK."""
        self.session.zeroize()
        for key in self.group_keys.values():
            key.wipe()

    def __repr__(self) -> str:
        """Render the keyring without its DEKs; group ids are fine to show, the DEKs themselves never are."""
        return (
            f"Keyring(enrollment_id={self.enrollment_id!r}, session={self.session!r}, "
            f"group_keys=<{len(self.group_keys)} redacted for {self.security_group_ids!r}>)"
        )
