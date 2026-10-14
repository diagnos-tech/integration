"""Every exception the SDK raises, in one place.

Callers catch by class, never by message. `VaultError` carries the vault's
`code`, HTTP status and `trace_id` so a support ticket can find the event on
the server side; the subclasses map the codes documented in
`docs/PROTOCOL.md §12` to the decision the caller has to make (retry, wait,
buy credit, re-enroll, fix the input).
"""

from __future__ import annotations


class DiagnosError(Exception):
    """Base of every SDK error."""


class ConfigError(DiagnosError):
    """Missing or malformed configuration, such as environment variables or the API token."""


class CryptoError(DiagnosError):
    """An envelope did not open or a format did not match the protocol.

    Deliberately one class: distinguishing "wrong key" from "tampered
    ciphertext" would hand an oracle to whoever is probing.
    """


class ProtocolError(DiagnosError):
    """The vault answered something the protocol does not allow, such as signing a size that is not the body's.

    This is not the caller's fault and is not retryable: report it with the
    SDK version, or upgrade if the vault has moved on.
    """


class VaultError(DiagnosError):
    """The vault answered with an error envelope."""

    code: str
    """The vault's error code (`QuotaExceeded`, `DocumentNotFound`, ...). Branch on it, never on `message`."""
    message: str
    """The vault's message, for a person."""
    status: int
    """The HTTP status the vault answered with."""
    trace_id: str | None
    """The vault's trace id, which a support ticket needs to find the event on the server side."""
    request_id: str | None
    """The `X-Request-Id` of the failed response."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Build the error from a vault error envelope.

        Args:
            code: The vault's error code.
            message: The vault's message, for a person.
            status: The HTTP status of the response; together with `code` it decides the subclass.
            trace_id: The vault's trace id, for finding the event server-side.
            request_id: The `X-Request-Id` of the failed response.
        """
        super().__init__(f"{code} ({status}): {message}")
        self.code = code
        self.message = message
        self.status = status
        self.trace_id = trace_id
        self.request_id = request_id


class ValidationError(VaultError):
    """HTTP 400 or 413: the request itself is wrong; fix the input."""


class AuthenticationError(VaultError):
    """HTTP 401: the token, session or signature was rejected; usually re-enroll."""


class QuotaError(VaultError):
    """HTTP 402: the workspace has no credit for this; nothing was done."""


class DiagnosPermissionError(VaultError):
    """HTTP 403: the service account may not do this here."""


class NotFoundError(VaultError):
    """HTTP 404: the resource does not exist, or is not visible to this account."""


class ConflictError(VaultError):
    """HTTP 409: the state disagrees with the request, for example a pending version or a replay."""


class RateLimitError(VaultError):
    """HTTP 429: slow down; the SDK has already retried with backoff."""


class EnrollmentDeniedError(DiagnosError):
    """A person denied this SDK session in the web app."""


class EnrollmentExpiredError(DiagnosError):
    """Nobody approved within the window; start again."""


class SessionExpiredError(DiagnosError):
    """The session keys are past `expires_at`; enroll again."""
