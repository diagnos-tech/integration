"""🇺🇸 The typed shapes an application actually holds: documents, records, drive nodes, pages.

Everything here is a `pydantic.BaseModel`, deliberately not a hand-rolled
`dataclass`: the SDK's whole external surface is data that just came off the
wire (`model_validate`) or is about to go on it (`model_dump_json`), and
pydantic is what turns "the vault sent a dict" into "either a typed object or
a `ValidationError` that names the exact field" without the SDK writing that
check by hand for every resource. Nothing here ever holds key material — a
`Patient`/`Exam` wraps an already-*decrypted* record, but the DEK that opened
it lives only in the `Keyring` (`session/keyring.py`) and is never a field on
any of these models, so a stray `repr()`, log line or `model_dump()` of one
of these objects can never leak a secret.

This is a package, not a single module, split by domain so no file grows
past the project's ~250-line convention: `_shared.py` (the caller-vs-vault
validation rule every sealed record builds on) and `_temporal.py` (date
parsing/writing) are the foundation; `_index.py` is the vault's own
bookkeeping (streams, versions, drafts, pagination); `_patients.py`/
`_exams.py` hold each domain's sealed record and summary; `_opened.py`
composes an index with a decrypted record into `Patient`/`Exam`; `_drives.py`
is the unrelated drive-node domain (`docs/PROTOCOL.md §9`). Every name a
caller could import from `diagnos.models` before this split is re-exported
here unchanged.

🇧🇷 As formas tipadas que uma aplicação de fato guarda: documentos, registros,
nós de drive, páginas.

Tudo aqui é um `pydantic.BaseModel`, de propósito não um `dataclass` feito à
mão: a superfície externa inteira do SDK é dado que acabou de chegar do fio
(`model_validate`) ou está prestes a ir (`model_dump_json`), e o pydantic é o
que transforma "o cofre mandou um dict" em "ou um objeto tipado ou um
`ValidationError` que nomeia o campo exato" sem o SDK escrever essa checagem
à mão para cada recurso. Nada aqui guarda material de chave — um
`Patient`/`Exam` embrulha um registro já *decifrado*, mas a DEK que o abriu
vive só no `Keyring` (`session/keyring.py`) e nunca é campo de nenhum destes
modelos, então um `repr()`, linha de log ou `model_dump()` acidental de um
destes objetos jamais consegue vazar um segredo.

Isto é um pacote, não um módulo único, dividido por domínio para nenhum
arquivo passar da convenção de ~250 linhas do projeto: `_shared.py` (a regra
de validação quem-chama-vs-cofre em que todo registro selado se apoia) e
`_temporal.py` (parsing/gravação de data) são a base; `_index.py` é o
controle que o próprio cofre mantém (fluxos, versões, rascunhos, paginação);
`_patients.py`/`_exams.py` guardam o registro selado e o resumo de cada
domínio; `_opened.py` compõe um índice com um registro decifrado em
`Patient`/`Exam`; `_drives.py` é o domínio à parte de nó de drive
(`docs/PROTOCOL.md §9`). Todo nome que quem chama pudesse importar de
`diagnos.models` antes desta divisão é reexportado aqui sem mudanças.
"""

from __future__ import annotations

from ._drives import (
    DriveMediaKind,
    DriveNode,
    DriveNodeKind,
    DriveNodeStatus,
    DriveUploadMode,
    OptimizedVariant,
    SecurityContext,
    StagedNode,
)
from ._exams import ExamRecord, ExamSummary
from ._index import (
    DocumentDraft,
    DocumentIndex,
    DocumentListItem,
    DocumentStream,
    DocumentVersion,
    Page,
    ResourceKind,
    StreamName,
    SummaryT,
    T,
)
from ._opened import Exam, Patient
from ._patients import (
    BiologicalSex,
    GenderIdentity,
    PatientAddress,
    PatientRecord,
    PatientSummary,
    PersonalIdentifier,
    RaceIdentity,
)
from ._shared import TYPO_CUTOFF, vault_context
from ._temporal import IsoInstant

# 🇺🇸 Generic aliases: a list row of one resource, parametrized on its own summary type.
# 🇧🇷 Aliases genéricos: uma linha de lista de um recurso, parametrizada no próprio tipo de resumo.
PatientListItem = DocumentListItem[PatientSummary]
ExamListItem = DocumentListItem[ExamSummary]

__all__ = [
    "TYPO_CUTOFF",
    "BiologicalSex",
    "DocumentDraft",
    "DocumentIndex",
    "DocumentListItem",
    "DocumentStream",
    "DocumentVersion",
    "DriveMediaKind",
    "DriveNode",
    "DriveNodeKind",
    "DriveNodeStatus",
    "DriveUploadMode",
    "Exam",
    "ExamListItem",
    "ExamRecord",
    "ExamSummary",
    "GenderIdentity",
    "IsoInstant",
    "OptimizedVariant",
    "Page",
    "Patient",
    "PatientAddress",
    "PatientListItem",
    "PatientRecord",
    "PatientSummary",
    "PersonalIdentifier",
    "RaceIdentity",
    "ResourceKind",
    "SecurityContext",
    "StagedNode",
    "StreamName",
    "SummaryT",
    "T",
    "vault_context",
]
