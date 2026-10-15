"""🇺🇸 Which module each public SDK name of `diagnos` lives in — data for the lazy loader in `diagnos/__init__.py`.

Standard library only, like the rest of the base: importing it never pulls
the SDK in. `wrappers/py/tests/test_facade.py` holds this map equal to the
`TYPE_CHECKING` imports of `diagnos/__init__.py` and `__all__` to their union.

🇧🇷 Em que módulo vive cada nome público do SDK do `diagnos` — dado do carregador preguiçoso de `__init__.py`.

Só biblioteca padrão, como o resto da base: importá-lo nunca puxa o SDK.
`wrappers/py/tests/test_facade.py` mantém este mapa igual aos imports de
`TYPE_CHECKING` de `diagnos/__init__.py` e o `__all__` igual à união deles.
"""

from __future__ import annotations

from typing import Final

SDK: Final[dict[str, tuple[str, ...]]] = {
    "._client_identity": ("LegacyTokenWarning",),
    ".client": ("Diagnos",),
    ".crypto.secure": ("MemoryLockWarning", "memory_status"),
    ".dates": ("TimePrecision", "to_iso_instant", "truncate_timestamp"),
    ".errors": (
        "AuthenticationError",
        "ClockSkewError",
        "ConfigError",
        "ConflictError",
        "CredentialError",
        "CredentialExpiredError",
        "CredentialReplayError",
        "CredentialRevokedError",
        "CredentialSignatureError",
        "CredentialUnknownError",
        "CryptoError",
        "DiagnosError",
        "DiagnosPermissionError",
        "EnrollmentDeniedError",
        "EnrollmentExpiredError",
        "NotFoundError",
        "ProtocolError",
        "QuotaError",
        "RateLimitError",
        "ScopeMissingError",
        "SessionExpiredError",
        "ValidationError",
        "VaultError",
        "WorkspaceMismatchError",
    ),
    ".models": (
        "DocumentDraft",
        "DocumentIndex",
        "DocumentListItem",
        "DocumentStream",
        "DocumentVersion",
        "DriveNode",
        "Exam",
        "ExamListItem",
        "ExamRecord",
        "ExamSummary",
        "Page",
        "Patient",
        "PatientAddress",
        "PatientListItem",
        "PatientRecord",
        "PatientSummary",
        "PersonalIdentifier",
    ),
    ".resources.drives": ("Drive", "Drives", "UploadSource"),
    ".resources.exams": ("Exams",),
    ".resources.patients": ("Patients",),
    ".session.enrollment": ("EnrollmentPrompt",),
    ".session.keyring": ("GroupKeyUnavailable",),
    ".transport.config": ("Settings",),
    ".transport.credential": ("ServiceAccountCredential",),
}
