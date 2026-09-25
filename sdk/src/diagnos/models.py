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

from collections.abc import Iterator
from datetime import date
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from diagnos.crypto import EncryptedPayload

ResourceKind = Literal["patients", "exams", "templates"]

T = TypeVar("T")


class DocumentVersion(BaseModel):
    """🇺🇸 One entry of `DocumentIndex.versions` (`docs/PROTOCOL.md §8`) — metadata only, never content.

    🇧🇷 Uma entrada de `DocumentIndex.versions` (`docs/PROTOCOL.md §8`) — só metadado, nunca conteúdo.
    """

    model_config = ConfigDict(frozen=True)

    version_id: str
    size: int
    created_at: str
    created_by: str


class DocumentIndex(BaseModel):
    """🇺🇸 The Firestore-backed index the vault exposes for a patient/exam/template (`docs/PROTOCOL.md §8`).

    Every field here is plaintext the vault itself reads to route and
    authorize — `security_groups`, `encrypted_keys` and `meta` are the only
    things the server knows about a document. The clinical content
    (`PatientRecord`/`ExamRecord`) never appears on this model; it lives one
    level down, in the encrypted R2 object `VersionedDocuments.read` opens.

    🇧🇷 O índice apoiado em Firestore que o cofre expõe para um
    paciente/exame/modelo (`docs/PROTOCOL.md §8`).

    Todo campo aqui é texto claro que o próprio cofre lê para rotear e
    autorizar — `security_groups`, `encrypted_keys` e `meta` são a única
    coisa que o servidor sabe sobre um documento. O conteúdo clínico
    (`PatientRecord`/`ExamRecord`) nunca aparece neste modelo; ele vive um
    nível abaixo, no objeto cifrado do R2 que `VersionedDocuments.read` abre.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    workspace_id: str
    resource: ResourceKind
    security_groups: list[str]
    encrypted_keys: dict[str, EncryptedPayload]
    latest_version_id: str | None = None
    versions: list[DocumentVersion] = Field(default_factory=list)
    pending_version_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str | None = None
    is_archived: bool = False
    is_deleted: bool = False


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


class PatientRecord(BaseModel):
    """🇺🇸 The clinical content of a patient document (`docs/PROTOCOL.md §8`) — everything that gets encrypted.

    `extra="forbid"`: this record is serialized (`model_dump_json`) straight
    into the object the vault stores forever, so a typo'd field name should
    fail loud, locally, before a single byte is encrypted — not silently
    vanish into a dict the vault can never validate (it never sees plaintext).

    🇧🇷 O conteúdo clínico de um documento de paciente (`docs/PROTOCOL.md
    §8`) — tudo que é cifrado.

    `extra="forbid"`: este registro é serializado (`model_dump_json`) direto
    para o objeto que o cofre guarda para sempre, então um nome de campo
    digitado errado deve falhar alto, localmente, antes de um único byte ser
    cifrado — não sumir em silêncio num dict que o cofre nunca pode validar
    (ele nunca vê texto claro).
    """

    model_config = ConfigDict(extra="forbid")

    legal_name: str
    display_name: str
    legal_id: str | None = None
    external_id: str | None = None
    birth_date: date | None = None
    biological_sex: BiologicalSex | None = None
    gender_identity: GenderIdentity | None = None
    race_identity: RaceIdentity | None = None
    internal_notes: list[str] | None = None
    email: str | None = None
    phone: str | None = None
    custom_attributes: dict[str, Any] | None = None


ReportFormat = Literal["html", "markdown", "text"]


class ReportContent(BaseModel):
    """🇺🇸 An exam's report body, in whichever of the three formats it was authored (`docs/PROTOCOL.md §8`).

    🇧🇷 O corpo do laudo de um exame, em qualquer um dos três formatos em que foi redigido (`docs/PROTOCOL.md §8`).
    """

    model_config = ConfigDict(extra="forbid")

    format: ReportFormat
    content: str


class ExamRecord(BaseModel):
    """🇺🇸 The clinical content of an exam document (`docs/PROTOCOL.md §8`) — everything that gets encrypted.

    `patient_id` and `modality` are deliberately absent here: they live in
    `DocumentIndex.meta`, in plaintext, because the vault itself routes and
    authorizes by them (`Exams.create`'s `meta` argument) — duplicating them
    inside the encrypted record would let the two copies drift.

    🇧🇷 O conteúdo clínico de um documento de exame (`docs/PROTOCOL.md §8`) — tudo que é cifrado.

    `patient_id` e `modality` estão ausentes daqui de propósito: vivem em
    `DocumentIndex.meta`, em claro, porque o próprio cofre roteia e autoriza
    por eles (argumento `meta` de `Exams.create`) — duplicá-los dentro do
    registro cifrado deixaria as duas cópias divergirem.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    report: ReportContent | None = None
    custom_attributes: dict[str, Any] | None = None


class Patient(BaseModel):
    """🇺🇸 A patient as an application actually wants it: the index plus its decrypted record, paired.

    🇧🇷 Um paciente do jeito que uma aplicação de fato quer: o índice mais o registro decifrado, pareados.
    """

    model_config = ConfigDict(frozen=True)

    index: DocumentIndex
    record: PatientRecord

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
    def security_groups(self) -> list[str]:
        """🇺🇸 Shorthand for `index.security_groups`. 🇧🇷 Atalho para `index.security_groups`."""
        return self.index.security_groups


class Exam(BaseModel):
    """🇺🇸 An exam as an application actually wants it: the index plus its decrypted record, paired.

    🇧🇷 Um exame do jeito que uma aplicação de fato quer: o índice mais o registro decifrado, pareados.
    """

    model_config = ConfigDict(frozen=True)

    index: DocumentIndex
    record: ExamRecord

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
    def security_groups(self) -> list[str]:
        """🇺🇸 Shorthand for `index.security_groups`. 🇧🇷 Atalho para `index.security_groups`."""
        return self.index.security_groups

    @property
    def patient_id(self) -> str | None:
        """🇺🇸 The exam's owning patient, read from clear `meta` (`docs/PROTOCOL.md §8`) — never guessed from content.

        🇧🇷 O paciente dono do exame, lido do `meta` em claro (`docs/PROTOCOL.md §8`) — nunca adivinhado do conteúdo.
        """
        patient_id = self.index.meta.get("patient_id")
        return str(patient_id) if patient_id is not None else None


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
