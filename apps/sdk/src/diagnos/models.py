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
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar, Final, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from diagnos.crypto import EncryptedPayload
from diagnos.dates import to_iso_instant

ResourceKind = Literal["patients", "exams", "templates"]
StreamName = Literal["data", "file"]

T = TypeVar("T")
SummaryT = TypeVar("SummaryT", bound=BaseModel)

# 🇺🇸 Validation-context key that marks "this came from the vault, not from the caller" (see `_Record`).
# 🇧🇷 Chave do contexto de validação que marca "isto veio do cofre, não de quem chama" (ver `_Record`).
_FROM_VAULT: Final[str] = "diagnos.from_vault"


def vault_context() -> dict[str, bool]:
    """🇺🇸 The pydantic validation context the SDK uses for plaintext it just decrypted.

    Records built by the caller are strict (an unknown field is a typo and
    fails before anything is encrypted); records decrypted from the vault are
    tolerant (a field the web app added later is kept, so a read-modify-write
    round trip never drops it). This context is what tells the two apart.

    🇧🇷 O contexto de validação do pydantic que o SDK usa para o texto claro que acabou de decifrar.

    Registros montados por quem chama são estritos (um campo desconhecido é
    erro de digitação e falha antes de qualquer coisa ser cifrada);
    registros decifrados do cofre são tolerantes (um campo que o app web
    acrescentou depois é mantido, então um ciclo ler-modificar-gravar nunca
    o perde). Este contexto é o que separa os dois.
    """
    return {_FROM_VAULT: True}


def _from_vault(info: ValidationInfo) -> bool:
    """🇺🇸 `True` when validating plaintext the SDK decrypted. 🇧🇷 `True` ao validar texto claro que o SDK decifrou."""
    return bool(info.context and info.context.get(_FROM_VAULT))


def _instant(value: str) -> datetime | None:
    """🇺🇸 `Date.parse` for the precedence rule: an aware `datetime`, or `None` when unparseable.

    🇧🇷 O `Date.parse` da regra de precedência: um `datetime` com fuso, ou `None` quando não dá para ler.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


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


def _iso_instant(value: Any, info: ValidationInfo) -> Any:
    """🇺🇸 Accepts a `date`/aware `datetime` and writes it the way the web app does (`YYYY-MM-DDTHH:MM:SS.sssZ`).

    A string from the caller must parse as ISO 8601; a string from the
    vault is kept exactly as stored.

    🇧🇷 Aceita `date`/`datetime` com fuso e grava do jeito que o app web grava (`YYYY-MM-DDTHH:MM:SS.sssZ`).

    Uma string de quem chama precisa ser ISO 8601 válida; uma string vinda
    do cofre fica exatamente como foi gravada.
    """
    if value is None or _from_vault(info):
        return value
    return to_iso_instant(value)


# 🇺🇸 A date field: `date`/aware `datetime`/ISO string in, the web app's UTC instant string out.
# 🇧🇷 Um campo de data: `date`/`datetime` com fuso/string ISO na entrada, o instante UTC do app web na saída.
IsoInstant = Annotated[str | None, BeforeValidator(_iso_instant)]


# 🇺🇸 How close an unknown key must be to a real field to count as a typo (`difflib` ratio).
# 🇧🇷 Quão perto de um campo real uma chave desconhecida precisa estar para contar como erro de digitação.
TYPO_CUTOFF: Final[float] = 0.8


class _Record(BaseModel):
    """🇺🇸 Base of every sealed record: typo-proof for the caller, lossless for fields the SDK does not model.

    The vault never sees plaintext, so nothing downstream validates a
    record: this model is the last check before encryption. Two failure
    modes pull in opposite directions, and the rule below handles both:

    - A **typo** (`birthdate` for `birth_date`) would store the value under
      a key nobody reads. Any unknown key that closely resembles a real
      field is refused, naming the field it resembles.
    - A **field the web app added** before this SDK modelled it must survive
      a read-modify-write — `get()`, change one thing, `update()` — or the
      SDK would silently delete clinical data. Any other unknown key is kept
      verbatim (`extra="allow"`), in the order it came.

    Plaintext decrypted from the vault skips the typo check entirely: it is
    what the web app wrote, not something the caller typed.

    🇧🇷 Base de todo registro selado: à prova de erro de digitação para quem chama, sem perda para
    campos que o SDK não modela.

    O cofre nunca vê texto claro, então nada adiante valida um registro:
    este modelo é a última checagem antes da cifragem. Duas falhas puxam
    em direções opostas, e a regra abaixo cobre as duas:

    - Um **erro de digitação** (`birthdate` por `birth_date`) guardaria o
      valor numa chave que ninguém lê. Toda chave desconhecida muito
      parecida com um campo real é recusada, nomeando o campo parecido.
    - Um **campo que o app web acrescentou** antes de este SDK modelá-lo
      precisa sobreviver a um ler-modificar-gravar — `get()`, mudar uma
      coisa, `update()` — senão o SDK apagaria dado clínico em silêncio.
      Qualquer outra chave desconhecida é mantida como veio (`extra="allow"`).

    Texto claro decifrado do cofre pula a checagem de digitação: é o que o
    app web gravou, não algo que quem chama digitou.
    """

    # 🇺🇸 `hide_input_in_errors`: a validation error names the field, never echoes the clinical value (logs).
    # 🇧🇷 `hide_input_in_errors`: um erro de validação nomeia o campo, nunca ecoa o valor clínico (logs).
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)

    # 🇺🇸 Keys that belong somewhere else (a method argument, clear `meta`), with where they go.
    # 🇧🇷 Chaves que pertencem a outro lugar (um argumento de método, o `meta` em claro), com o destino.
    _MISPLACED: ClassVar[dict[str, str]] = {}

    @model_validator(mode="before")
    @classmethod
    def _reject_typos(cls, data: Any, info: ValidationInfo) -> Any:
        """🇺🇸 Refuses unknown keys that look like a misspelled field (or belong elsewhere), naming the fix.

        🇧🇷 Recusa chaves desconhecidas que parecem um campo digitado errado (ou de outro lugar), nomeando a correção.
        """
        if _from_vault(info) or not isinstance(data, Mapping):
            return data
        misplaced = [f"{key!r}: {cls._MISPLACED[key]}" for key in data if key in cls._MISPLACED]
        if misplaced:
            raise ValueError(f"{cls.__name__}: {'; '.join(misplaced)}")
        known = set(cls.model_fields)
        typos = {}
        for key in data:
            if key in known:
                continue
            close = difflib.get_close_matches(str(key), known, n=1, cutoff=TYPO_CUTOFF)
            if close:
                typos[key] = close[0]
        if not typos:
            return data
        hints = ", ".join(f"{key!r} → {field!r}" for key, field in typos.items())
        raise ValueError(
            f"{cls.__name__}: unknown field that looks like a typo, did you mean: {hints} · campo desconhecido "
            f"com cara de erro de digitação, quis dizer: {hints}"
        )


BiologicalSex = Literal["MALE", "FEMALE", "INTERSEX", "UNDEFINED"]
GenderIdentity = Literal[
    "CIS_MALE",
    "CIS_FEMALE",
    "TRANS_MALE",
    "TRANS_FEMALE",
    "NON_BINARY",
    "AGENDER",
    "FLUID",
    "OTHER",
    "PREFER_NOT_TO_SAY",
]
RaceIdentity = Literal["WHITE", "BLACK", "BROWN", "YELLOW", "INDIGENOUS", "NOT_DECLARED"]

# 🇺🇸 `secret:v1:<salt>:<iv>:<payload>` — a value the vault sealed through its sensitive-data route.
# 🇧🇷 `secret:v1:<salt>:<iv>:<payload>` — um valor que o cofre selou pela rota de dado sensível.
_SEALED_SECRET = re.compile(r"^secret:v1:[^:]+:[^:]+:[^:]+$")


class PersonalIdentifier(_Record):
    """🇺🇸 An identity document (CPF, RG, passport…) whose `value` is sealed by the vault, not by this SDK.

    Opening one is audited server-side, which is why the value is
    `secret:v1:…` sealed material rather than plain text. The external API
    has no route to seal a new one yet: records read from the vault carry
    them through untouched, and a caller-built record must already hold
    sealed values. For a plain id from another system, use
    `PatientRecord.external_id`.

    🇧🇷 Um documento de identidade (CPF, RG, passaporte…) cujo `value` é selado pelo cofre, não por este SDK.

    Abrir um é auditado no servidor, por isso o valor é material selado
    `secret:v1:…` e não texto claro. A API externa ainda não tem rota para
    selar um novo: registros lidos do cofre os carregam intactos, e um
    registro montado por quem chama já precisa trazer valores selados. Para
    um id simples de outro sistema, use `PatientRecord.external_id`.
    """

    name: str = Field(min_length=1)
    value: str

    @field_validator("value")
    @classmethod
    def _value_is_sealed(cls, value: str, info: ValidationInfo) -> str:
        """🇺🇸 Refuses a plain-text identifier. 🇧🇷 Recusa um identificador em texto claro."""
        if _from_vault(info) or _SEALED_SECRET.match(value):
            return value
        raise ValueError(
            "identifiers[].value must be vault-sealed material ('secret:v1:…'); plain-text identity documents "
            "are never stored — use external_id for a plain id · identifiers[].value precisa ser material selado "
            "pelo cofre ('secret:v1:…'); documento de identidade em texto claro nunca é gravado — use external_id"
        )


class PatientAddress(_Record):
    """🇺🇸 A patient's address; every field optional (an emergency registration may have none).

    🇧🇷 O endereço de um paciente; todo campo opcional (um cadastro de emergência pode não ter nenhum).
    """

    postal_code: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class PatientRecord(_Record):
    """🇺🇸 The `data` stream of a patient (`PatientData` in the web app) — everything here is sealed before upload.

    `birth_date` accepts a `date` or an aware `datetime` and is stored the
    way the web app stores it, as a UTC ISO 8601 instant. Set
    `Settings.time_precision` to truncate it to the workspace's
    anonymization precision before sealing, like the web app does.

    🇧🇷 O fluxo `data` de um paciente (`PatientData` no app web) — tudo aqui é selado antes do upload.

    `birth_date` aceita `date` ou `datetime` com fuso e é gravado do jeito
    que o app web grava, como um instante ISO 8601 em UTC. Defina
    `Settings.time_precision` para truncá-lo à precisão de anonimização do
    workspace antes de selar, como o app web faz.
    """

    _MISPLACED: ClassVar[dict[str, str]] = {
        "tags": "not a record field — pass tags=[...] to create/update · não é campo do registro — passe tags=[...]",
        "specialist_ids": "clear metadata — pass specialist_ids=[...] to create/update · metadado em claro — passe "
        "specialist_ids=[...]",
    }

    legal_name: str
    display_name: str
    identifiers: list[PersonalIdentifier] | None = None
    external_id: str | None = None
    birth_date: IsoInstant = None
    biological_sex: BiologicalSex | None = None
    gender_identity: GenderIdentity | None = None
    race_identity: RaceIdentity | None = None
    email: str | None = None
    phone: str | None = None
    address: PatientAddress | None = None
    internal_notes: list[str] | None = None
    custom_attributes: dict[str, Any] | None = None


class ExamRecord(_Record):
    """🇺🇸 The content of an exam version (`ExamContent` in the web app) — the report and its clinical context.

    `report_lexical` is the web editor's state (Lexical JSON, as a string)
    and is the source of truth; `report_html` is derived from it for readers
    that never open the editor. Write both when you produce a report, or the
    web editor opens an empty document.

    🇧🇷 O conteúdo de uma versão de exame (`ExamContent` no app web) — o laudo e o contexto clínico.

    `report_lexical` é o estado do editor web (JSON do Lexical, como string)
    e é a fonte da verdade; `report_html` é derivado dele para leitores que
    nunca abrem o editor. Grave os dois ao produzir um laudo, senão o editor
    web abre um documento vazio.
    """

    _MISPLACED: ClassVar[dict[str, str]] = {
        "patient_id": "clear metadata — pass patient_id=... to Exams.create · metadado em claro — passe patient_id=...",
        "report": "the report is report_lexical (editor state) plus report_html · o laudo é report_lexical (estado do "
        "editor) mais report_html",
    }

    title: str | None = None
    modality: str | None = None
    exam_date: IsoInstant = None
    report_lexical: str | None = None
    report_html: str | None = None
    custom_attributes: dict[str, Any] | None = None


class PatientSummary(BaseModel):
    """🇺🇸 The plaintext of a patient's `encrypted_index`: what a list shows without opening any version.

    The SDK derives it from the record on every write (plus `tags`, which
    are not a record field); it never carries identity documents, because
    opening the summary is not audited.

    🇧🇷 O texto claro do `encrypted_index` de um paciente: o que uma lista mostra sem abrir nenhuma versão.

    O SDK o deriva do registro a cada gravação (mais `tags`, que não são
    campo do registro); ele nunca carrega documento de identidade, porque
    abrir o resumo não é auditado.
    """

    model_config = ConfigDict(frozen=True, extra="allow", hide_input_in_errors=True)

    display_name: str | None = None
    legal_name: str | None = None
    external_id: str | None = None
    birth_date: str | None = None
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def of(cls, record: PatientRecord, tags: Sequence[str]) -> PatientSummary:
        """🇺🇸 The summary the web app would write for `record`. 🇧🇷 O resumo que o app web gravaria para `record`."""
        return cls(
            display_name=record.display_name,
            legal_name=record.legal_name,
            external_id=record.external_id,
            birth_date=record.birth_date,
            tags=list(tags),
        )


class ExamSummary(BaseModel):
    """🇺🇸 The plaintext of an exam's `encrypted_index`: title, modality and date, derived from the record.

    🇧🇷 O texto claro do `encrypted_index` de um exame: título, modalidade e data, derivados do registro.
    """

    model_config = ConfigDict(frozen=True, extra="allow", hide_input_in_errors=True)

    title: str | None = None
    modality: str | None = None
    exam_date: str | None = None

    @classmethod
    def of(cls, record: ExamRecord) -> ExamSummary:
        """🇺🇸 The summary the web app would write for `record`. 🇧🇷 O resumo que o app web gravaria para `record`."""
        return cls(title=record.title, modality=record.modality, exam_date=record.exam_date)


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


PatientListItem = DocumentListItem[PatientSummary]
ExamListItem = DocumentListItem[ExamSummary]


class _OpenedDocument(BaseModel):
    """🇺🇸 Fields shared by `Patient` and `Exam`: the index, where the content came from, and shorthands.

    🇧🇷 Campos comuns a `Patient` e `Exam`: o índice, de onde veio o conteúdo, e atalhos.
    """

    model_config = ConfigDict(frozen=True)

    index: DocumentIndex
    version_id: str | None = None
    """🇺🇸 The committed version the record came from; `None` when it came from the draft head.

    🇧🇷 A versão confirmada de onde o registro veio; `None` quando veio da cabeça de rascunho.
    """
    draft_rev: int | None = None
    """🇺🇸 The draft revision the record came from, when the draft was newer.

    🇧🇷 A revisão do rascunho de onde o registro veio, quando ele era mais novo.
    """

    @property
    def id(self) -> str:
        """🇺🇸 The document id — shorthand for `index.document_id`.

        🇧🇷 O id do documento — atalho para `index.document_id`.
        """
        return self.index.document_id

    @property
    def updated_at(self) -> str:
        """🇺🇸 Shorthand for `index.updated_at`. 🇧🇷 Atalho para `index.updated_at`."""
        return self.index.updated_at

    @property
    def security_group_id(self) -> str:
        """🇺🇸 Shorthand for `index.security_group_id`. 🇧🇷 Atalho para `index.security_group_id`."""
        return self.index.security_group_id

    @property
    def from_draft(self) -> bool:
        """🇺🇸 `True` when the record is the (newer) draft head, not a committed version.

        🇧🇷 `True` quando o registro é a cabeça de rascunho (mais nova), não uma versão confirmada.
        """
        return self.draft_rev is not None


class Patient(_OpenedDocument):
    """🇺🇸 A patient as an application wants it: the index, the decrypted record and its summary.

    🇧🇷 Um paciente do jeito que uma aplicação quer: o índice, o registro decifrado e o resumo.
    """

    record: PatientRecord
    summary: PatientSummary | None = None

    @property
    def tags(self) -> list[str]:
        """🇺🇸 The sealed list/search tags (`summary.tags`). 🇧🇷 As tags seladas de lista/busca (`summary.tags`)."""
        return list(self.summary.tags) if self.summary is not None else []


class Exam(_OpenedDocument):
    """🇺🇸 An exam as an application wants it: the index, the decrypted record and its summary.

    🇧🇷 Um exame do jeito que uma aplicação quer: o índice, o registro decifrado e o resumo.
    """

    record: ExamRecord
    summary: ExamSummary | None = None

    @property
    def patient_id(self) -> str | None:
        """🇺🇸 The exam's patient, read from clear `meta` (`docs/PROTOCOL.md §8`) — never guessed from content.

        🇧🇷 O paciente do exame, lido do `meta` em claro (`docs/PROTOCOL.md §8`) — nunca adivinhado do conteúdo.
        """
        patient_id = self.index.meta.get("patient_id")
        return str(patient_id) if patient_id is not None else None

    @property
    def report_status(self) -> str | None:
        """🇺🇸 `draft` or `published`, from clear `meta`; `None` when never set.

        🇧🇷 `draft` ou `published`, do `meta` em claro; `None` quando nunca definido.
        """
        status = self.index.meta.get("report_status")
        return str(status) if status is not None else None


DriveNodeStatus = Literal["pending", "ready", "failed"]
DriveUploadMode = Literal["single", "multipart"]
DriveMediaKind = Literal["image", "video", "dicom", "other"]


class DriveNode(BaseModel):
    """🇺🇸 One file in a drive (`docs/PROTOCOL.md §9`) — the vault's index of it, never its content.

    Mirrors the vault's own response shape one field for one field, minus
    `reservation` (an internal usage-metering detail with no meaning to an
    SDK caller — see `resources/drives.py`'s module docstring). `encrypted_name`
    stays sealed here; only `Drive.name_of` decrypts it, on demand, because
    doing it eagerly on every list page would mean deriving a key and
    running AES-GCM for files nobody asked to see the name of.

    🇧🇷 Um arquivo num drive (`docs/PROTOCOL.md §9`) — o índice que o cofre
    tem dele, nunca o conteúdo.

    Espelha a forma de resposta do próprio cofre campo a campo, menos
    `reservation` (um detalhe interno de medição de uso sem sentido para
    quem chama o SDK — ver a docstring do módulo `resources/drives.py`).
    `encrypted_name` fica selado aqui; só `Drive.name_of` decifra, sob
    demanda, porque fazer isso de forma antecipada em toda página de lista
    significaria derivar uma chave e rodar AES-GCM para arquivos que
    ninguém pediu para ver o nome.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    workspace_id: str
    security_group_id: str
    exam_id: str | None = None
    parent_id: str | None = None
    status: DriveNodeStatus
    mode: DriveUploadMode
    declared_size: int
    size: int | None = None
    mime_type: str | None = None
    media_kind: DriveMediaKind
    encrypted_name: EncryptedPayload | None = None
    part_size: int | None = None
    part_count: int | None = None
    storage_path: str
    created_by: str
    created_at: str
    completed_at: str | None = None


class UploadedNode(BaseModel):
    """🇺🇸 One entry of the `POST {base}/uploads` staging response (`docs/PROTOCOL.md §9`) — a plan, not a finished node.

    Internal to `resources/drives.py`: `Drive.upload`/`upload_many` consume
    this to know, per file, whether to run the single-PUT path (`upload` is
    set) or the multipart path (`part_size`/`part_count` are set) — a caller
    of the SDK never sees this shape, only the finished `DriveNode` `upload`
    returns once the content actually lands.

    🇧🇷 Uma entrada da resposta de reserva de `POST {base}/uploads`
    (`docs/PROTOCOL.md §9`) — um plano, não um nó terminado.

    Interno a `resources/drives.py`: `Drive.upload`/`upload_many` consomem
    isto para saber, por arquivo, se seguem o caminho de PUT único (`upload`
    presente) ou o multipart (`part_size`/`part_count` presentes) — quem usa
    o SDK nunca vê esta forma, só o `DriveNode` terminado que `upload`
    devolve quando o conteúdo de fato chega.
    """

    model_config = ConfigDict(frozen=True)

    client_ref: str
    node_id: str
    mode: DriveUploadMode
    upload: dict[str, Any] | None = None
    part_size: int | None = None
    part_count: int | None = None
