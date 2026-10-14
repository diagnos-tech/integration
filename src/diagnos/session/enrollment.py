"""Enrollment: how an SDK process earns a session and the group keys it may use."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from diagnos import __version__
from diagnos.crypto.envelope import EncryptedPayload
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import SecretBox
from diagnos.errors import (
    CryptoError,
    DiagnosError,
    EnrollmentDeniedError,
    EnrollmentExpiredError,
    NotFoundError,
)
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.runtime import collect_runtime

# Deferred to type-checking only: `diagnos.transport` eagerly imports
# `diagnos.session.keyring` (for `VaultTransport`'s own type hints), so a
# module-level import here, of a *submodule* of `diagnos.transport`, would
# close a real import cycle the moment anything imports `diagnos.transport`
# before `diagnos.session`. Nothing below needs the classes at runtime: it
# only calls duck-typed methods and attributes (`transport.post(...)`,
# `token.workspace_id`) that never require the class object itself.
if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport
    from diagnos.transport.token import ServiceAccountToken

# The one shape every group DEK must have (`docs/PROTOCOL.md §5`): raw
# AES-256-GCM key material, nothing wrapped around it. A wrong length can
# only mean a protocol mismatch, never a recoverable state, so it fails
# loudly instead of silently truncating or padding.
_GROUP_KEY_LENGTH = 32


@dataclass(frozen=True)
class EnrollmentPrompt:
    """What a human needs to see: the link to open and the code to type.

    Attributes:
        enrollment_id: The id of the pending enrollment.
        approval_url: The web app link where a workspace admin approves the enrollment.
        code: The code the approver types or compares to confirm it is this enrollment.
        expires_at: When the approval window closes, in Unix seconds.
    """

    enrollment_id: str
    approval_url: str
    code: str
    expires_at: int


PromptCallback = Callable[[EnrollmentPrompt], None]


def _registry_path(workspace_id: str) -> str:
    """Return the unsigned enrollment route whose prefix both the `POST` and the `GET` poll share."""
    return f"/api/external/v1/workspaces/{workspace_id}/session/registry"


def _open_session(keypair: HybridKeyPair, enrollment_id: str, sealed_session: Any) -> SessionKeys:
    """Open `sealed_session` (AAD = `enrollment_id`) into `SessionKeys`; both keys are born inside the enclave."""
    payload = EncryptedPayload.from_dict(sealed_session)
    opened = keypair.open_session(payload, enrollment_id)
    return SessionKeys(
        session_id=opened.session_id,
        sign_key=opened.sign_key,
        enc_key=opened.enc_key,
        expires_at=opened.expires_at,
    )


def _open_group_keys(keypair: HybridKeyPair, enrollment_id: str, sealed_group_keys: Any) -> dict[str, SecretBox]:
    """Open every `sealed_group_keys[sg]` (AAD = `enrollment_id`) into a locked 32-byte DEK."""
    group_keys: dict[str, SecretBox] = {}
    for security_group_id, sealed in dict(sealed_group_keys or {}).items():
        payload = EncryptedPayload.from_dict(sealed)
        dek = keypair.open_secret(payload, enrollment_id)
        if len(dek) != _GROUP_KEY_LENGTH:
            dek.wipe()
            raise CryptoError(
                f"group DEK for {security_group_id!r} opened to {len(dek)} bytes, expected {_GROUP_KEY_LENGTH}."
            )
        group_keys[security_group_id] = dek
    return group_keys


def enroll(
    transport: VaultTransport,
    token: ServiceAccountToken,
    keypair: HybridKeyPair,
    *,
    on_prompt: PromptCallback,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> Keyring:
    """Register the key pair, show the prompt, poll until approved, and open the sealed material.

    Both the registration `POST` and the poll `GET` go out `signed=False`
    (`docs/PROTOCOL.md §5`): a signature would need a session's `sign_key`,
    and the entire point of this call is that no session exists yet. Bearer
    auth alone is enough to prove which service account is asking, and the
    approval itself is the human decision that grants everything else.

    Args:
        transport: The HTTP transport used for the registration and the poll.
        token: The parsed service-account token, which names the workspace.
        keypair: The identity whose public keys are registered and whose secrets open the approval.
        on_prompt: Called once with the approval link and code so a person can approve.
        sleep: The sleep function used between polls; replaced in tests.
        now: The clock, in Unix seconds; replaced in tests.

    Returns:
        The keyring holding the session keys and every approved group DEK.

    Raises:
        EnrollmentExpiredError: If nobody approved before the window closed.
        EnrollmentDeniedError: If a workspace admin denied the enrollment.
        CryptoError: If the approval does not open, or a group DEK has the wrong length.
        DiagnosError: If the poll returns a status this SDK does not know.
    """
    path = _registry_path(token.workspace_id)
    registration = transport.post(
        path,
        json={
            "public_keys": keypair.public_keys_b64url(),
            "runtime": collect_runtime(__version__),
        },
        signed=False,
    )

    enrollment_id: str = registration["enrollment_id"]
    prompt = EnrollmentPrompt(
        enrollment_id=enrollment_id,
        approval_url=registration["approval_url"],
        code=registration["code"],
        expires_at=registration["expires_at"],
    )
    on_prompt(prompt)

    poll_interval_seconds: float = registration["poll_interval_seconds"]
    poll_path = f"{path}/{enrollment_id}"

    while True:
        if now() >= prompt.expires_at:
            raise EnrollmentExpiredError("nobody approved this enrollment before it expired; start again.")

        try:
            poll_result = transport.get(poll_path, signed=False)
        except NotFoundError as exc:
            # The vault itself drops an enrollment past its deadline
            # (`SdkEnrollmentNotFound`). A 404 arriving after `expires_at`
            # means the same thing as our own clock check above catching it
            # first: either way, the window is closed.
            raise EnrollmentExpiredError(
                "the vault no longer knows this enrollment; the approval window closed."
            ) from exc

        status = poll_result["status"]
        if status == "pending":
            sleep(poll_interval_seconds)
            continue
        if status == "denied":
            raise EnrollmentDeniedError("a workspace admin denied this SDK session.")
        if status == "approved":
            approval = poll_result["approval"]
            session = _open_session(keypair, enrollment_id, approval["sealed_session"])
            group_keys = _open_group_keys(keypair, enrollment_id, approval.get("sealed_group_keys"))
            return Keyring(enrollment_id=enrollment_id, session=session, group_keys=group_keys)

        raise DiagnosError(f"session/registry poll returned unknown status {status!r}.")
