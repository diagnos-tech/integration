"""🇺🇸 Shared constants and small free functions the document engine's read and write paths both lean on.

`OpenedDocument` and `coerce_record` are what `resources/patients.py`/
`resources/exams.py` see; the retry/paging budgets and stream layout table
are read by both `_reading.py` and `_writing.py` — keeping them here (rather
than duplicated, or hidden as class attributes) means there is exactly one
place that names, say, how many times a `DocumentVersionPending` reservation
is retried.

🇧🇷 Constantes e pequenas funções livres em que os caminhos de leitura e escrita do motor de documento se apoiam.

`OpenedDocument` e `coerce_record` são o que `resources/patients.py`/
`resources/exams.py` veem; os orçamentos de retentativa/paginação e a
tabela de fluxos são lidos por `_reading.py` e `_writing.py` — mantê-los
aqui (em vez de duplicados, ou escondidos como atributos de classe)
significa que existe exatamente um lugar que nomeia, por exemplo, quantas
vezes uma reserva `DocumentVersionPending` é retentada.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Generic, TypeVar

import httpx
from pydantic import BaseModel

from diagnos.errors import VaultError
from diagnos.models import DocumentIndex, ResourceKind, StreamName

RecordT = TypeVar("RecordT", bound=BaseModel)
SummaryT = TypeVar("SummaryT", bound=BaseModel)

# 🇺🇸 §13: list pages cap at 200; 50 mirrors the web app's own default.
# 🇧🇷 §13: páginas de lista têm teto de 200; 50 espelha o padrão do próprio app web.
DEFAULT_PAGE_SIZE: Final[int] = 50

# 🇺🇸 Which streams each resource has — this decides the shape of the version URLs: a
#    multi-stream resource carries `/streams/{stream}`, a single-stream one does not.
# 🇧🇷 Quais fluxos cada recurso tem — isto decide a forma das URLs de versão: um recurso
#    de vários fluxos carrega `/streams/{fluxo}`, um de fluxo único não.
STREAMS_BY_RESOURCE: Final[dict[ResourceKind, tuple[StreamName, ...]]] = {
    "patients": ("data", "file"),
    "exams": ("data",),
    "templates": ("data",),
}

# 🇺🇸 The structured-record stream: the only one the SDK reads and writes (patients' `file` stream is
#    the web editor's binary Lexical/Yjs document, not a record).
# 🇧🇷 O fluxo do registro estruturado: o único que o SDK lê e grava (o fluxo `file` de pacientes é o
#    documento binário Lexical/Yjs do editor web, não um registro).
DATA_STREAM: Final[StreamName] = "data"

# 🇺🇸 Same budgets as the web app: a reservation refused because another writer holds the pending
#    slot is retried briefly; a commit lost to the network is retried with backoff (it is idempotent).
# 🇧🇷 Mesmos orçamentos do app web: uma reserva recusada porque outro escritor segura o slot
#    pendente é retentada por pouco tempo; um commit perdido na rede é retentado com backoff (é idempotente).
STAGE_PENDING_ATTEMPTS: Final[int] = 3
STAGE_PENDING_BACKOFF_SECONDS: Final[float] = 1.5
COMMIT_ATTEMPTS: Final[int] = 3
COMMIT_BACKOFF_SECONDS: Final[float] = 0.5

# 🇺🇸 SSE-C header names the vault lists in `upload.headers`/`client_headers` (see `_put_headers`).
# 🇧🇷 Nomes de header de SSE-C que o cofre lista em `upload.headers`/`client_headers` (ver `_put_headers`).
_SSE_C_HEADER_PREFIX: Final[str] = "x-amz-server-side-encryption-customer-"


def coerce_record(model: type[RecordT], value: RecordT | Mapping[str, Any]) -> RecordT:
    """🇺🇸 Accepts a model instance as-is, or validates a plain `dict` into one.

    The one place `Patients`/`Exams` let a caller pass `{"legal_name": ...}`
    instead of constructing `PatientRecord(...)` first — good REPL ergonomics
    without weakening validation, since a `dict` still goes through the same
    pydantic model (and its unknown-field check) either way.

    🇧🇷 Aceita uma instância do modelo como está, ou valida um `dict` puro nela.

    O único lugar onde `Patients`/`Exams` deixam quem chama passar
    `{"legal_name": ...}` em vez de construir `PatientRecord(...)` antes —
    boa ergonomia de REPL sem enfraquecer a validação, já que um `dict`
    passa pelo mesmo modelo pydantic (e a checagem de campo desconhecido)
    de qualquer jeito.
    """
    return value if isinstance(value, model) else model.model_validate(value)


@dataclass(frozen=True)
class OpenedDocument(Generic[RecordT, SummaryT]):
    """🇺🇸 What one read or write returns: the index, the record, its summary, and where the record came from.

    🇧🇷 O que uma leitura ou gravação devolve: o índice, o registro, o resumo, e de onde o registro veio.
    """

    index: DocumentIndex
    record: RecordT
    summary: SummaryT | None
    version_id: str | None
    draft_rev: int | None = None


def _is_retryable_commit_failure(error: Exception) -> bool:
    """🇺🇸 The network dropped, or the vault failed on its side — a commit replay is safe then.

    🇧🇷 A rede caiu, ou o cofre falhou do lado dele — reenviar o commit é seguro nesses casos.
    """
    if isinstance(error, httpx.TransportError):
        return True
    return isinstance(error, VaultError) and error.status is not None and error.status >= 500
