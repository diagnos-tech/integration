"""🇺🇸 The vault's index of a document (`docs/PROTOCOL.md §8`): streams, versions, drafts, pagination.

Everything here is what the vault itself reads to route and authorize a
patient/exam/template — never the clinical content, which lives only in a
sealed version object (`resources/_documents.py`) or the caller's decrypted
record (`_patients.py`/`_exams.py`).

🇧🇷 O índice que o cofre tem de um documento (`docs/PROTOCOL.md §8`): fluxos, versões, rascunhos, paginação.

Tudo aqui é o que o próprio cofre lê para rotear e autorizar um
paciente/exame/modelo — nunca o conteúdo clínico, que vive só num objeto de
versão selado (`resources/_documents.py`) ou no registro decifrado de quem
chama (`_patients.py`/`_exams.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from diagnos.crypto import EncryptedPayload

from ._temporal import _instant

ResourceKind = Literal["patients", "exams", "templates"]
StreamName = Literal["data", "file"]

T = TypeVar("T")
SummaryT = TypeVar("SummaryT", bound=BaseModel)


class DocumentVersion(BaseModel):
    """🇺🇸 One committed version of a stream (`docs/PROTOCOL.md §8`) — metadata only, never content.

    🇧🇷 Uma versão confirmada de um fluxo (`docs/PROTOCOL.md §8`) — só metadado, nunca conteúdo.
    """

    model_config = ConfigDict(frozen=True)

    version_id: str
    size: int
    created_at: str
    created_by: str


class DocumentDraft(BaseModel):
    """🇺🇸 A stream's mutable draft head: the web editor's autosave, overwritten in place, never a version.

    🇧🇷 A cabeça mutável de rascunho de um fluxo: o autosave do editor web, sobrescrito no lugar, nunca uma versão.
    """

    model_config = ConfigDict(frozen=True)

    rev: int
    size: int
    updated_at: str
    updated_by: str


class DocumentStream(BaseModel):
    """🇺🇸 One independent line of versions inside a document (`docs/PROTOCOL.md §8`).

    Exams and templates have a single stream, `data`. Patients have two:
    `data` (the structured record this SDK reads and writes) and `file` (the
    web editor's rich document, not exposed by the SDK yet).

    🇧🇷 Uma linha independente de versões dentro de um documento (`docs/PROTOCOL.md §8`).

    Exames e modelos têm um fluxo só, `data`. Pacientes têm dois: `data` (o
    registro estruturado que este SDK lê e grava) e `file` (o documento rico
    do editor web, ainda não exposto pelo SDK).
    """

    model_config = ConfigDict(frozen=True)

    latest_version_id: str | None = None
    versions: list[DocumentVersion] = Field(default_factory=list)
    pending_version_id: str | None = None
    draft: DocumentDraft | None = None

    @property
    def latest_version(self) -> DocumentVersion | None:
        """🇺🇸 The entry of `versions` that `latest_version_id` points at.

        🇧🇷 A entrada de `versions` que `latest_version_id` aponta.
        """
        return next((v for v in self.versions if v.version_id == self.latest_version_id), None)

    @property
    def draft_is_newer(self) -> bool:
        """🇺🇸 The web app's precedence rule: the draft wins when it exists and is newer than the latest version.

        A commit does not erase the draft, it only supersedes it, so "newer"
        is decided by timestamps: `draft.updated_at` against the latest
        version's `created_at`. An unreadable timestamp never makes the draft
        win — the committed version is the safe answer.

        🇧🇷 A regra de precedência do app web: o rascunho vence quando existe e é mais novo que a versão corrente.

        Um commit não apaga o rascunho, só o supera, então "mais novo" é
        decidido por horário: `draft.updated_at` contra o `created_at` da
        versão corrente. Um horário ilegível nunca faz o rascunho vencer — a
        versão confirmada é a resposta segura.
        """
        if self.draft is None:
            return False
        latest = self.latest_version
        if latest is None:
            return True
        draft_at, latest_at = _instant(self.draft.updated_at), _instant(latest.created_at)
        return draft_at is not None and latest_at is not None and draft_at > latest_at


class DocumentIndex(BaseModel):
    """🇺🇸 What the vault knows about a patient/exam/template (`docs/PROTOCOL.md §8`): keys, streams, clear metadata.

    Every field here is something the vault itself reads to route and
    authorize. The clinical content never appears on this model: it lives in
    the sealed object of each version, and a short sealed summary (name,
    title) lives in `encrypted_index`, which only a DEK holder opens.

    Exactly one `security_group_id` per document: sharing a patient with
    another team means copying it, never sharing its key.

    🇧🇷 O que o cofre sabe sobre um paciente/exame/modelo (`docs/PROTOCOL.md §8`): chaves, fluxos, metadado em claro.

    Todo campo aqui é algo que o próprio cofre lê para rotear e autorizar. O
    conteúdo clínico nunca aparece neste modelo: ele vive no objeto selado de
    cada versão, e um resumo selado curto (nome, título) vive em
    `encrypted_index`, que só quem tem a DEK abre.

    Exatamente um `security_group_id` por documento: compartilhar um
    paciente com outra equipe é copiá-lo, nunca compartilhar a chave.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    workspace_id: str
    resource: ResourceKind
    security_group_id: str
    encrypted_keys: dict[str, EncryptedPayload]
    encrypted_index: EncryptedPayload | None = None
    streams: dict[StreamName, DocumentStream] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str | None = None
    is_archived: bool = False
    is_deleted: bool = False

    @field_validator("meta", mode="before")
    @classmethod
    def _meta_absent_is_empty(cls, value: Any) -> Any:
        """🇺🇸 The vault omits `meta` when a document has none. 🇧🇷 O cofre omite `meta` quando o documento não tem."""
        return {} if value is None else value

    def stream(self, name: StreamName = "data") -> DocumentStream:
        """🇺🇸 One stream's state; an empty stream when the vault sent none for `name`.

        🇧🇷 O estado de um fluxo; um fluxo vazio quando o cofre não mandou nenhum para `name`.
        """
        return self.streams.get(name) or DocumentStream()

    @property
    def latest_version_id(self) -> str | None:
        """🇺🇸 Shorthand for `stream("data").latest_version_id`. 🇧🇷 Atalho para `stream("data").latest_version_id`."""
        return self.stream().latest_version_id

    @property
    def versions(self) -> list[DocumentVersion]:
        """🇺🇸 Shorthand for `stream("data").versions`. 🇧🇷 Atalho para `stream("data").versions`."""
        return self.stream().versions

    @property
    def pending_version_id(self) -> str | None:
        """🇺🇸 Shorthand for `stream("data").pending_version_id`. 🇧🇷 Atalho para `stream("data").pending_version_id`."""
        return self.stream().pending_version_id


class Page(BaseModel, Generic[T]):
    """🇺🇸 One page of a cursor-paginated list (`docs/PROTOCOL.md §8`/`§9`): `items` plus the cursor for the next call.

    `__iter__` yields `items` directly (not pydantic's default field-tuple
    iteration) so `for item in vault.patients.list(): ...` reads the way any
    Python sequence does — the field-tuple behaviour nobody wants here is
    still reachable through `dict(page)` if it were ever needed.

    🇧🇷 Uma página de uma lista paginada por cursor (`docs/PROTOCOL.md
    §8`/`§9`): `items` mais o cursor para a próxima chamada.

    `__iter__` entrega `items` direto (não a iteração padrão do pydantic
    sobre pares campo-valor) para `for item in vault.patients.list(): ...`
    ler como qualquer sequência Python — o comportamento de tupla de campos
    que ninguém quer aqui ainda seria alcançável via `dict(page)` se um dia
    precisasse.
    """

    model_config = ConfigDict(frozen=True)

    items: list[T]
    next_cursor: str | None = None

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        """🇺🇸 Iterate `items`, not pydantic's default `(field, value)` pairs.

        🇧🇷 Itera `items`, não os pares `(campo, valor)` padrão do pydantic.
        """
        return iter(self.items)


class DocumentListItem(BaseModel, Generic[SummaryT]):
    """🇺🇸 One row of a list: the index plus its decrypted summary — no version downloaded.

    `summary` is `None` when the document predates `encrypted_index` or
    belongs to a security group this session holds no key for.

    🇧🇷 Uma linha de lista: o índice mais o resumo decifrado — nenhuma versão baixada.

    `summary` é `None` quando o documento é anterior ao `encrypted_index` ou
    pertence a um security group para o qual esta sessão não tem chave.
    """

    model_config = ConfigDict(frozen=True)

    index: DocumentIndex
    summary: SummaryT | None = None

    @property
    def id(self) -> str:
        """🇺🇸 Shorthand for `index.document_id`. 🇧🇷 Atalho para `index.document_id`."""
        return self.index.document_id
