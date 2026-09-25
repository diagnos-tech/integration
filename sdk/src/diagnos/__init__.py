"""🇺🇸 diagnos — zero-knowledge SDK for the diagnos vault.

Everything an application needs is reachable from this top-level package:
`Diagnos` is the entry point, `Settings` configures it, the record/model
types shape what `patients`/`exams` read and write, and the exceptions are
what a caller catches. Anything not exported here — `diagnos.resources`,
`diagnos.session`, `diagnos.transport`, `diagnos.crypto` — is internal
plumbing `cli`/`api` and application code are not meant to import directly
(`CONVENTIONS.md`): if something in there is missing from this list, that is
a gap in the SDK's public surface, not a signal to reach past it.

🇧🇷 diagnos — SDK zero-knowledge do cofre diagnos.

Tudo que uma aplicação precisa é alcançável a partir deste pacote de
primeiro nível: `Diagnos` é o ponto de entrada, `Settings` o configura, os
tipos de registro/modelo dão forma ao que `patients`/`exams` leem e
escrevem, e as exceções são o que quem chama captura. Qualquer coisa não
exportada aqui — `diagnos.resources`, `diagnos.session`,
`diagnos.transport`, `diagnos.crypto` — é encanamento interno que `cli`/`api`
e código de aplicação não devem importar direto (`CONVENTIONS.md`): se algo
lá dentro está faltando nesta lista, é uma lacuna na superfície pública do
SDK, não um sinal para alcançar por cima dela.
"""

from __future__ import annotations

from ._version import __version__
from .client import Diagnos
from .crypto.secure import MemoryLockWarning, memory_status
from .errors import (
    AuthenticationError,
    ConfigError,
    ConflictError,
    CryptoError,
    DiagnosError,
    DiagnosPermissionError,
    EnrollmentDeniedError,
    EnrollmentExpiredError,
    NotFoundError,
    QuotaError,
    RateLimitError,
    SessionExpiredError,
    ValidationError,
    VaultError,
)
from .models import (
    DocumentIndex,
    DriveNode,
    Exam,
    ExamRecord,
    Page,
    Patient,
    PatientRecord,
)
from .resources.drives import Drive, Drives
from .session.enrollment import EnrollmentPrompt
from .session.keyring import GroupKeyUnavailable
from .transport.config import Settings

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "ConflictError",
    "CryptoError",
    "DocumentIndex",
    "Drive",
    "DriveNode",
    "Drives",
    "EnrollmentDeniedError",
    "EnrollmentExpiredError",
    "EnrollmentPrompt",
    "Exam",
    "ExamRecord",
    "GroupKeyUnavailable",
    "Diagnos",
    "DiagnosError",
    "DiagnosPermissionError",
    "MemoryLockWarning",
    "NotFoundError",
    "Page",
    "Patient",
    "PatientRecord",
    "QuotaError",
    "RateLimitError",
    "SessionExpiredError",
    "Settings",
    "ValidationError",
    "VaultError",
    "__version__",
    "memory_status",
]
