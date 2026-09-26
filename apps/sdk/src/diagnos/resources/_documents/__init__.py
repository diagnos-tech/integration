"""🇺🇸 `VersionedDocuments`: the one engine behind patients, exams and templates (`docs/PROTOCOL.md §8`).

`resources/patients.py` and `resources/exams.py` are thin, resource-specific
faces (they know the record type, the summary and the clear `meta`); every
byte of protocol — paths, keys, sealing, upload, commit — lives here once,
and follows the web app step for step, because a document is only useful if
both of them can open it:

- **Keys.** One DEK per document, sealed under the key of the document's
  single security group with `DOCUMENT_DEK_INFO`. Each stored object gets its
  own content key, derived from the DEK and the `security_context` the vault
  hands out next to the signed URL (`crypto/content.py`).
- **Writing** is two-phase: reserve (`POST`, which returns a signed `PUT`
  URL locked to the exact sealed size) → `PUT` the sealed bytes → commit.
  Every version is a complete record, never a delta. The sealed summary
  (`encrypted_index`) travels with the reservation.
- **Reading** follows the web app's precedence rule: the stream's draft head
  (the editor's autosave) wins when it is newer than the latest version.
- **Archive/delete** are patch-only reservations: no new version, no upload.

This is a package, not a single module, so no file grows past the project's
~250-line convention: `_support.py` holds the constants and small free
functions both directions share; `_base.py` is construction, URL shape and
key handling; `_reading.py` and `_writing.py` are the two halves of the
protocol, as mixins `VersionedDocuments` below stitches together. Every name
importable from `diagnos.resources._documents` before this split is
re-exported here unchanged.

🇧🇷 `VersionedDocuments`: o único motor por trás de pacientes, exames e modelos (`docs/PROTOCOL.md §8`).

`resources/patients.py` e `resources/exams.py` são faces finas por recurso
(conhecem o tipo do registro, o resumo e o `meta` em claro); todo byte de
protocolo — paths, chaves, selagem, upload, commit — vive aqui uma vez, e
segue o app web passo a passo, porque um documento só serve se os dois
conseguem abri-lo:

- **Chaves.** Uma DEK por documento, selada sob a chave do único security
  group do documento com `DOCUMENT_DEK_INFO`. Cada objeto guardado ganha a
  própria chave de conteúdo, derivada da DEK e do `security_context` que o
  cofre entrega junto da URL assinada (`crypto/content.py`).
- **Gravar** é em duas fases: reservar (`POST`, que devolve uma URL de `PUT`
  assinada travada no tamanho selado exato) → `PUT` dos bytes selados →
  commit. Toda versão é um registro completo, nunca um delta. O resumo
  selado (`encrypted_index`) viaja com a reserva.
- **Ler** segue a regra de precedência do app web: a cabeça de rascunho do
  fluxo (o autosave do editor) vence quando é mais nova que a versão corrente.
- **Arquivar/apagar** são reservas só de patch: sem versão nova, sem upload.

Isto é um pacote, não um módulo único, para nenhum arquivo passar da
convenção de ~250 linhas do projeto: `_support.py` guarda as constantes e
pequenas funções livres que as duas direções compartilham; `_base.py` é
construção, forma de URL e manejo de chaves; `_reading.py` e `_writing.py`
são as duas metades do protocolo, como mixins que `VersionedDocuments`
abaixo costura. Todo nome importável de `diagnos.resources._documents`
antes desta divisão é reexportado aqui sem mudanças.
"""

from __future__ import annotations

from ._reading import _Reading
from ._support import _SSE_C_HEADER_PREFIX as _SSE_C_HEADER_PREFIX
from ._support import (
    COMMIT_ATTEMPTS,
    COMMIT_BACKOFF_SECONDS,
    DATA_STREAM,
    DEFAULT_PAGE_SIZE,
    STAGE_PENDING_ATTEMPTS,
    STAGE_PENDING_BACKOFF_SECONDS,
    STREAMS_BY_RESOURCE,
    OpenedDocument,
    RecordT,
    SummaryT,
    coerce_record,
)
from ._support import _is_retryable_commit_failure as _is_retryable_commit_failure
from ._writing import _Writing

__all__ = [
    "COMMIT_ATTEMPTS",
    "COMMIT_BACKOFF_SECONDS",
    "DATA_STREAM",
    "DEFAULT_PAGE_SIZE",
    "STAGE_PENDING_ATTEMPTS",
    "STAGE_PENDING_BACKOFF_SECONDS",
    "STREAMS_BY_RESOURCE",
    "OpenedDocument",
    "VersionedDocuments",
    "coerce_record",
]


class VersionedDocuments(_Reading[RecordT, SummaryT], _Writing[RecordT, SummaryT]):
    """🇺🇸 One resource (`patients`/`exams`/`templates`) of one workspace, generic over record and summary types.

    Assembled from `_Reading` and `_Writing` (both built on `_DocumentsBase`
    for construction, URL shape and key handling); nothing is added here —
    this class exists so the two halves have one name and one instance.

    🇧🇷 Um recurso (`patients`/`exams`/`templates`) de um workspace, genérico nos tipos de registro e resumo.

    Montada a partir de `_Reading` e `_Writing` (ambas construídas sobre
    `_DocumentsBase` para construção, forma de URL e manejo de chaves); nada
    é acrescentado aqui — esta classe existe para as duas metades terem um
    nome e uma instância só.
    """
