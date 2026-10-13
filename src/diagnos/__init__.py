"""🇺🇸 diagnos — the diagnos vault from Python: zero-knowledge SDK, command line and REST API, in one package.

`import diagnos` is cheap and always works, even on the base install: the
SDK's public names below are loaded on first use, so `pip install diagnos`
(the `diagnos docs | version | setup | help` wrapper) never pays for — or
needs — httpx, pydantic or the Rust enclave. With `diagnos[sdk]` installed,
`from diagnos import Diagnos` behaves exactly as an eager import would;
without it, it raises `MissingExtraError` naming the command that adds it.

Everything an application needs is reachable from here: `Diagnos` is the
entry point, `Settings` configures it, the record/model types shape what
`patients`/`exams` read and write, and the exceptions are what a caller
catches. Anything not exported here — `diagnos.resources`,
`diagnos.session`, `diagnos.transport`, `diagnos.crypto` — is internal
plumbing `diagnos.cli`/`diagnos.api` and application code are not meant to
import directly (`CONTRIBUTING.md`): if something in there is missing from
this list, that is a gap in the SDK's public surface, not a signal to reach
past it.

🇧🇷 diagnos — o cofre diagnos no Python: SDK zero-knowledge, linha de comando e API REST, num pacote só.

`import diagnos` é barato e sempre funciona, mesmo na instalação base: os
nomes públicos do SDK abaixo são carregados no primeiro uso, então o
`pip install diagnos` (o wrapper `diagnos docs | version | setup | help`)
nunca paga por — nem precisa de — httpx, pydantic ou o enclave Rust. Com o
`diagnos[sdk]` instalado, `from diagnos import Diagnos` se comporta
exatamente como um import imediato; sem ele, lança `MissingExtraError`
nomeando o comando que o soma.

Tudo que uma aplicação precisa é alcançável daqui: `Diagnos` é o ponto de
entrada, `Settings` o configura, os tipos de registro/modelo dão forma ao
que `patients`/`exams` leem e escrevem, e as exceções são o que quem chama
captura. Qualquer coisa não exportada aqui — `diagnos.resources`,
`diagnos.session`, `diagnos.transport`, `diagnos.crypto` — é encanamento
interno que `diagnos.cli`/`diagnos.api` e código de aplicação não devem
importar direto (`CONTRIBUTING.md`): se algo lá dentro está faltando nesta
lista, é uma lacuna na superfície pública do SDK, não um sinal para alcançar
por cima dela.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Final

from ._extras import MissingExtraError, require
from ._version import __version__

if TYPE_CHECKING:
    from .client import Diagnos
    from .crypto.secure import MemoryLockWarning, memory_status
    from .dates import TimePrecision, to_iso_instant, truncate_timestamp
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
        ProtocolError,
        QuotaError,
        RateLimitError,
        SessionExpiredError,
        ValidationError,
        VaultError,
    )
    from .models import (
        DocumentDraft,
        DocumentIndex,
        DocumentListItem,
        DocumentStream,
        DocumentVersion,
        DriveNode,
        Exam,
        ExamListItem,
        ExamRecord,
        ExamSummary,
        Page,
        Patient,
        PatientAddress,
        PatientListItem,
        PatientRecord,
        PatientSummary,
        PersonalIdentifier,
    )
    from .resources.drives import Drive, Drives, UploadSource
    from .resources.exams import Exams
    from .resources.patients import Patients
    from .session.enrollment import EnrollmentPrompt
    from .session.keyring import GroupKeyUnavailable
    from .transport.config import Settings

# 🇺🇸 The same imports as the `TYPE_CHECKING` block above, as data: which module each public SDK name lives in.
#    `wrappers/py/tests/test_facade.py` holds the two lists equal and `__all__` to their union.
# 🇧🇷 Os mesmos imports do bloco `TYPE_CHECKING` acima, como dado: em que módulo vive cada nome público do SDK.
#    O `wrappers/py/tests/test_facade.py` mantém as duas listas iguais e o `__all__` igual à união delas.
_SDK: Final[dict[str, tuple[str, ...]]] = {
    ".client": ("Diagnos",),
    ".crypto.secure": ("MemoryLockWarning", "memory_status"),
    ".dates": ("TimePrecision", "to_iso_instant", "truncate_timestamp"),
    ".errors": (
        "AuthenticationError",
        "ConfigError",
        "ConflictError",
        "CryptoError",
        "DiagnosError",
        "DiagnosPermissionError",
        "EnrollmentDeniedError",
        "EnrollmentExpiredError",
        "NotFoundError",
        "ProtocolError",
        "QuotaError",
        "RateLimitError",
        "SessionExpiredError",
        "ValidationError",
        "VaultError",
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
}
_ORIGIN: Final = {name: module for module, names in _SDK.items() for name in names}


def _load(name: str) -> object:
    """🇺🇸 Imports one public SDK name on first use and caches it here, so the next access is a plain attribute.

    🇧🇷 Importa um nome público do SDK no primeiro uso e o guarda aqui, para o próximo acesso ser atributo simples.
    """
    module = _ORIGIN.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    require("sdk", f"diagnos.{name}")
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """🇺🇸 What is here plus what loads on first use, for completion. 🇧🇷 O que está aqui mais o que carrega no uso."""
    return sorted({*globals(), *_ORIGIN})


# 🇺🇸 Hidden from type checkers on purpose: a module-level `__getattr__` makes them accept any attribute
#    (`diagnos.Diagnoss` would type-check); the `TYPE_CHECKING` imports already tell them the real names.
# 🇧🇷 Escondido dos verificadores de tipo de propósito: um `__getattr__` de módulo os faz aceitar qualquer atributo
#    (`diagnos.Diagnoss` passaria); os imports de `TYPE_CHECKING` já lhes dizem os nomes de verdade.
if not TYPE_CHECKING:  # pragma: no branch — always true at runtime
    __getattr__ = _load

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "ConflictError",
    "CryptoError",
    "Diagnos",
    "DiagnosError",
    "DiagnosPermissionError",
    "DocumentDraft",
    "DocumentIndex",
    "DocumentListItem",
    "DocumentStream",
    "DocumentVersion",
    "Drive",
    "DriveNode",
    "Drives",
    "EnrollmentDeniedError",
    "EnrollmentExpiredError",
    "EnrollmentPrompt",
    "Exam",
    "ExamListItem",
    "Exams",
    "ExamRecord",
    "ExamSummary",
    "GroupKeyUnavailable",
    "MemoryLockWarning",
    "MissingExtraError",
    "NotFoundError",
    "Page",
    "Patient",
    "PatientAddress",
    "PatientListItem",
    "PatientRecord",
    "PatientSummary",
    "Patients",
    "PersonalIdentifier",
    "ProtocolError",
    "QuotaError",
    "RateLimitError",
    "SessionExpiredError",
    "Settings",
    "TimePrecision",
    "UploadSource",
    "ValidationError",
    "VaultError",
    "memory_status",
    "to_iso_instant",
    "truncate_timestamp",
    "__version__",
]
