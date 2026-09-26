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
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Generic, TypeVar

import httpx
from pydantic import BaseModel

from diagnos.crypto import (
    DOCUMENT_DEK_INFO,
    INDEX_INFO,
    SEALED_OVERHEAD_BYTES,
    EntropyMixer,
    SecretBox,
    decrypt_content,
    draft_key_id,
    encrypt_content,
    generate_dek,
    open_draft_content,
    open_version_content,
    seal_version_content,
    unwrap_key,
    wrap_key,
)
from diagnos.errors import ConflictError, CryptoError, ProtocolError, VaultError
from diagnos.models import DocumentIndex, DocumentListItem, Page, ResourceKind, StreamName, vault_context
from diagnos.session.keyring import Keyring

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport

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


class VersionedDocuments(Generic[RecordT, SummaryT]):
    """🇺🇸 One resource (`patients`/`exams`/`templates`) of one workspace, generic over record and summary types.

    🇧🇷 Um recurso (`patients`/`exams`/`templates`) de um workspace, genérico nos tipos de registro e resumo.
    """

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
        resource: ResourceKind,
        record_model: type[RecordT],
        summary_model: type[SummaryT],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """🇺🇸 `keyring_provider` is a callback (not a `Keyring`) so a lazy/auto-unlocking caller always asks fresh.

        🇧🇷 `keyring_provider` é um callback (não um `Keyring`) para quem chama
        de forma preguiçosa/auto-unlock sempre pedir um atual.
        """
        self._transport = transport
        self._keyring_provider = keyring_provider
        self._entropy = entropy
        self._resource = resource
        self._record_model = record_model
        self._summary_model = summary_model
        self._sleep = sleep
        # 🇺🇸 Parametrized once, so each list row validates *and serializes* as the concrete summary type.
        # 🇧🇷 Parametrizado uma vez, para cada linha validar *e serializar* como o tipo concreto do resumo.
        self._item_model: type[DocumentListItem[SummaryT]] = DocumentListItem[summary_model]  # type: ignore[valid-type]
        self._multi_stream = len(STREAMS_BY_RESOURCE[resource]) > 1
        self._base = f"/api/external/v1/workspaces/{workspace_id}/{resource}"

    # -- paths ---------------------------------------------------------------

    def _stream_path(self, document_id: str) -> str:
        """🇺🇸 `{base}/{id}` plus `/streams/data` on a multi-stream resource — where versions and drafts live.

        🇧🇷 `{base}/{id}` mais `/streams/data` num recurso de vários fluxos — onde vivem versões e rascunhos.
        """
        segment = f"/streams/{DATA_STREAM}" if self._multi_stream else ""
        return f"{self._base}/{document_id}{segment}"

    def _stream_query(self) -> dict[str, str | int | bool] | None:
        """🇺🇸 `?stream=data` on a multi-stream resource, so `GET {base}/{id}` answers about the data stream.

        🇧🇷 `?stream=data` num recurso de vários fluxos, para `GET {base}/{id}` responder sobre o fluxo de dados.
        """
        return {"stream": DATA_STREAM} if self._multi_stream else None

    # -- keys ----------------------------------------------------------------

    def _document_dek(self, index: DocumentIndex, keyring: Keyring | None = None) -> SecretBox:
        """🇺🇸 Unwraps the document's DEK with the key of its security group.

        🇧🇷 Desembrulha a DEK do documento com a chave do security group dele.
        """
        keyring = keyring or self._keyring_provider()
        group_id = index.security_group_id
        wrapped = index.encrypted_keys.get(group_id)
        if wrapped is None:
            raise CryptoError(
                f"🇺🇸 document {index.document_id!r} has no DEK sealed for its own security group {group_id!r}. "
                f"🇧🇷 o documento {index.document_id!r} não tem DEK selada para o próprio security group {group_id!r}."
            )
        return unwrap_key(keyring.group_key(group_id), wrapped, DOCUMENT_DEK_INFO)

    def _open_summary(self, index: DocumentIndex, dek: SecretBox) -> SummaryT | None:
        """🇺🇸 Decrypts `encrypted_index`; `None` for a document written before the field existed.

        🇧🇷 Decifra o `encrypted_index`; `None` para um documento gravado antes de o campo existir.
        """
        if index.encrypted_index is None:
            return None
        plaintext = decrypt_content(dek, index.encrypted_index, INDEX_INFO[self._resource])
        return self._summary_model.model_validate_json(plaintext)

    def _seal_summary(self, dek: SecretBox, summary: SummaryT) -> dict[str, str]:
        """🇺🇸 `encrypted_index` for `summary`, absent fields left out like `JSON.stringify` does.

        🇧🇷 O `encrypted_index` de `summary`, campos ausentes deixados de fora como o `JSON.stringify` faz.
        """
        plaintext = summary.model_dump_json(exclude_none=True).encode("utf-8")
        return encrypt_content(dek, plaintext, INDEX_INFO[self._resource]).to_dict()

    # -- listing -------------------------------------------------------------

    def list(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[DocumentListItem[SummaryT]]:
        """🇺🇸 One page of the index (`GET {base}`), each row with its summary already decrypted.

        No version is downloaded: the summary comes from `encrypted_index`,
        which is what lets the web app render a list of names offline. A row
        whose group key this session does not hold keeps `summary=None`
        instead of failing the whole page.

        🇧🇷 Uma página do índice (`GET {base}`), cada linha com o resumo já decifrado.

        Nenhuma versão é baixada: o resumo vem do `encrypted_index`, que é o
        que deixa o app web mostrar uma lista de nomes offline. Uma linha
        cujo grupo esta sessão não tem chave fica com `summary=None` em vez
        de derrubar a página inteira.
        """
        # 🇺🇸 The keyring first: asking for it is what unlocks lazily (`Diagnos._keyring_provider`), and a
        #    signed request cannot go out before there is a session — so `list()` may be a program's first call.
        # 🇧🇷 O keyring primeiro: pedi-lo é o que desbloqueia de forma preguiçosa (`Diagnos._keyring_provider`), e
        #    uma requisição assinada não sai antes de existir sessão — então `list()` pode ser a primeira chamada.
        keyring = self._keyring_provider()
        query: dict[str, str | int | bool] = {"limit": limit}
        if security_group is not None:
            query["security_group_id"] = security_group
        if include_deleted:
            query["include_deleted"] = "true"
        if cursor is not None:
            query["cursor"] = cursor
        result = self._transport.get(self._base, query=query)
        items = [self._list_item(DocumentIndex.model_validate(raw), keyring) for raw in result["items"]]
        return Page(items=items, next_cursor=result.get("next_cursor"))

    def _list_item(self, index: DocumentIndex, keyring: Keyring) -> DocumentListItem[SummaryT]:
        """🇺🇸 One list row: the index plus its summary when this session can open it.

        🇧🇷 Uma linha da lista: o índice mais o resumo quando esta sessão consegue abri-lo.
        """
        if index.encrypted_index is None or index.security_group_id not in keyring.security_group_ids:
            return self._item_model(index=index)
        summary = self._open_summary(index, self._document_dek(index, keyring))
        return self._item_model(index=index, summary=summary)

    def iter_all(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[DocumentListItem[SummaryT]]:
        """🇺🇸 Walks every page by following `next_cursor` until it is `None`.

        🇧🇷 Percorre toda página seguindo `next_cursor` até ele ser `None`.
        """
        cursor: str | None = None
        while True:
            page = self.list(security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor)
            yield from page.items
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def get_index(self, document_id: str) -> DocumentIndex:
        """🇺🇸 The index alone, discarding the `version`/`download` half of `GET {base}/{id}`.

        There is no lighter route for "just the index": this spends one
        unused presign for callers that only need metadata.

        🇧🇷 Só o índice, descartando a metade `version`/`download` de `GET {base}/{id}`.

        Não existe rota mais leve para "só o índice": isto gasta um presign
        não usado para quem só precisa do metadado.
        """
        result = self._transport.get(f"{self._base}/{document_id}", query=self._stream_query())
        return DocumentIndex.model_validate(result["document"])

    # -- reading -------------------------------------------------------------

    def read(
        self, document_id: str, *, version_id: str | None = None, include_draft: bool = True
    ) -> OpenedDocument[RecordT, SummaryT]:
        """🇺🇸 Fetches, downloads and decrypts one document — a pinned version, or the newest content.

        Without `version_id`, the newest content wins, exactly as in the web
        app: the draft head when it is newer than the latest version, else
        the latest version. `include_draft=False` always reads the latest
        committed version.

        🇧🇷 Busca, baixa e decifra um documento — uma versão fixada, ou o conteúdo mais novo.

        Sem `version_id`, o conteúdo mais novo vence, exatamente como no app
        web: a cabeça de rascunho quando é mais nova que a versão corrente,
        senão a versão corrente. `include_draft=False` sempre lê a última
        versão confirmada.
        """
        keyring = self._keyring_provider()  # 🇺🇸 lazy unlock first (see `list`) 🇧🇷 unlock preguiçoso antes
        query = self._stream_query() or {}
        if version_id is not None:
            query["version_id"] = version_id
        result = self._transport.get(f"{self._base}/{document_id}", query=query or None)
        index = DocumentIndex.model_validate(result["document"])
        dek = self._document_dek(index, keyring)
        summary = self._open_summary(index, dek)

        if version_id is None and include_draft and index.stream(DATA_STREAM).draft_is_newer:
            draft = self._transport.get(f"{self._stream_path(document_id)}/draft")
            if draft is not None:
                sealed = self._transport.download_bytes(draft["download"]["url"])
                key_id = draft_key_id(DATA_STREAM, multi_stream=self._multi_stream)
                plaintext = open_draft_content(dek, key_id, draft["security_context"]["value"], sealed)
                record = self._parse_record(plaintext)
                return OpenedDocument(index, record, summary, version_id=None, draft_rev=int(draft["draft_rev"]))

        opened_version_id = str(result["version"]["version_id"])
        sealed = self._transport.download_bytes(result["download"]["url"])
        plaintext = open_version_content(dek, opened_version_id, result["security_context"]["value"], sealed)
        return OpenedDocument(index, self._parse_record(plaintext), summary, version_id=opened_version_id)

    def _parse_record(self, plaintext: bytes) -> RecordT:
        """🇺🇸 Validates decrypted plaintext, tolerant of fields the SDK does not model yet.

        🇧🇷 Valida o texto claro decifrado, tolerante a campos que o SDK ainda não modela.
        """
        return self._record_model.model_validate_json(plaintext, context=vault_context())

    # -- writing -------------------------------------------------------------

    @staticmethod
    def _serialize(record: RecordT) -> bytes:
        """🇺🇸 The record as JSON, absent fields left out (`exclude_none`), as the web app writes it.

        🇧🇷 O registro como JSON, campos ausentes deixados de fora (`exclude_none`), como o app web grava.
        """
        return record.model_dump_json(exclude_none=True).encode("utf-8")

    @staticmethod
    def _put_headers(upload: Mapping[str, Any]) -> dict[str, str]:
        """🇺🇸 The `PUT` headers: what the vault fixed (`content-length`), minus SSE-C.

        The vault also names SSE-C headers for documents, but the web app
        does not use SSE-C on documents: it neither sends the key on the
        `PUT` nor on the `GET`. An object stored with SSE-C could only be
        read with that key, so the web app could never open a document the
        SDK wrote that way. Leaving the whole SSE-C trio out keeps both sides
        reading the same plain object (the body is end-to-end encrypted
        either way; SSE-C was only ever a second layer).

        🇧🇷 Os headers do `PUT`: o que o cofre fixou (`content-length`), menos SSE-C.

        O cofre também nomeia headers de SSE-C para documentos, mas o app
        web não usa SSE-C em documento: não manda a chave nem no `PUT` nem no
        `GET`. Um objeto guardado com SSE-C só seria lido com essa chave,
        então o app web nunca abriria um documento que o SDK gravasse assim.
        Deixar o trio de SSE-C de fora mantém os dois lados lendo o mesmo
        objeto simples (o corpo é cifrado ponta a ponta de qualquer jeito; o
        SSE-C sempre foi só uma segunda camada).
        """
        headers = upload.get("headers") or {}
        return {
            name: str(value) for name, value in headers.items() if not name.lower().startswith(_SSE_C_HEADER_PREFIX)
        }

    def _upload(self, staged: Mapping[str, Any], dek: SecretBox, plaintext: bytes) -> None:
        """🇺🇸 Seals `plaintext` for the reserved version and `PUT`s it to the signed URL.

        🇧🇷 Sela `plaintext` para a versão reservada e faz `PUT` na URL assinada.
        """
        sealed = seal_version_content(dek, staged["version_id"], staged["security_context"]["value"], plaintext)
        headers = self._put_headers(staged["upload"])
        declared = headers.get("content-length")
        if declared is not None and int(declared) != len(sealed):
            raise ProtocolError(
                f"🇺🇸 the vault signed {declared} bytes but the sealed version has {len(sealed)}. "
                f"🇧🇷 o cofre assinou {declared} bytes mas a versão selada tem {len(sealed)}."
            )
        self._transport.upload_bytes(staged["upload"]["url"], sealed, headers)

    def _stage(self, document_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """🇺🇸 `POST {stream}/versions`, retrying briefly while another writer holds the pending slot.

        🇧🇷 `POST {fluxo}/versions`, retentando por pouco tempo enquanto outro escritor segura o slot pendente.
        """
        path = f"{self._stream_path(document_id)}/versions"
        for attempt in range(1, STAGE_PENDING_ATTEMPTS + 1):
            try:
                result: dict[str, Any] = self._transport.post(path, json=dict(body))
                return result
            except ConflictError as exc:
                if exc.code != "DocumentVersionPending" or attempt == STAGE_PENDING_ATTEMPTS:
                    raise
                self._sleep(STAGE_PENDING_BACKOFF_SECONDS * attempt)
        raise AssertionError("unreachable · inalcançável")  # pragma: no cover

    def _commit(self, document_id: str, version_id: str) -> DocumentIndex:
        """🇺🇸 `POST {stream}/versions/{version_id}/commit`, retried with backoff — a replay is idempotent.

        🇧🇷 `POST {fluxo}/versions/{version_id}/commit`, retentado com backoff — reenviar é idempotente.
        """
        path = f"{self._stream_path(document_id)}/versions/{version_id}/commit"
        for attempt in range(1, COMMIT_ATTEMPTS + 1):
            try:
                result = self._transport.post(path)
                return DocumentIndex.model_validate(result["document"])
            except (httpx.TransportError, VaultError) as exc:
                if not _is_retryable_commit_failure(exc) or attempt == COMMIT_ATTEMPTS:
                    raise
                self._sleep(COMMIT_BACKOFF_SECONDS * 2 ** (attempt - 1))
        raise AssertionError("unreachable · inalcançável")  # pragma: no cover

    def create(
        self,
        record: RecordT,
        *,
        security_group: str,
        summary: SummaryT,
        meta: Mapping[str, Any] | None = None,
    ) -> OpenedDocument[RecordT, SummaryT]:
        """🇺🇸 Fresh DEK sealed for `security_group`, then reserve → `PUT` → commit the first version.

        🇧🇷 DEK nova selada para `security_group`, depois reservar → `PUT` → confirmar a primeira versão.
        """
        keyring = self._keyring_provider()
        group_key = keyring.group_key(security_group)
        dek = generate_dek(self._entropy)
        plaintext = self._serialize(record)
        body: dict[str, Any] = {
            "security_group_id": security_group,
            "encrypted_keys": {security_group: wrap_key(group_key, dek, DOCUMENT_DEK_INFO).to_dict()},
            "content_length": len(plaintext) + SEALED_OVERHEAD_BYTES,
            "encrypted_index": self._seal_summary(dek, summary),
            "stream": DATA_STREAM,
        }
        if meta:
            body["meta"] = dict(meta)
        staged = self._transport.post(self._base, json=body)
        document_id = str(staged["document"]["document_id"])
        self._upload(staged, dek, plaintext)
        index = self._commit(document_id, str(staged["version_id"]))
        return OpenedDocument(index, record, summary, version_id=str(staged["version_id"]))

    def update(
        self,
        document_id: str,
        record: RecordT,
        *,
        summary: Callable[[SummaryT | None], SummaryT],
        meta: Mapping[str, Any] | None = None,
        expected_latest_version_id: str | None = None,
    ) -> OpenedDocument[RecordT, SummaryT]:
        """🇺🇸 A new complete version of `record`, sealed under the document's existing DEK.

        `summary` maps the current summary (or `None`) to the new one, so a
        resource can carry forward what is not part of the record (a
        patient's `tags`). `expected_latest_version_id` makes the vault
        refuse the write (`409 DocumentVersionMismatch`) if someone else
        committed a version since you read it.

        🇧🇷 Uma versão nova e completa de `record`, selada sob a DEK existente do documento.

        `summary` transforma o resumo atual (ou `None`) no novo, para um
        recurso carregar adiante o que não é parte do registro (as `tags` de
        um paciente). `expected_latest_version_id` faz o cofre recusar a
        gravação (`409 DocumentVersionMismatch`) se outra pessoa confirmou
        uma versão depois da sua leitura.
        """
        keyring = self._keyring_provider()  # 🇺🇸 lazy unlock first (see `list`) 🇧🇷 unlock preguiçoso antes
        index = self.get_index(document_id)
        dek = self._document_dek(index, keyring)
        new_summary = summary(self._open_summary(index, dek))
        plaintext = self._serialize(record)
        body: dict[str, Any] = {
            "content_length": len(plaintext) + SEALED_OVERHEAD_BYTES,
            "encrypted_index": self._seal_summary(dek, new_summary),
        }
        if meta:
            body["meta"] = dict(meta)
        if expected_latest_version_id is not None:
            body["expected_latest_version_id"] = expected_latest_version_id
        staged = self._stage(document_id, body)
        if staged.get("staged") is not True:
            raise ProtocolError(
                "🇺🇸 the vault answered a version reservation as patch-only. "
                "🇧🇷 o cofre respondeu uma reserva de versão como só-patch."
            )
        self._upload(staged, dek, plaintext)
        committed = self._commit(document_id, str(staged["version_id"]))
        return OpenedDocument(committed, record, new_summary, version_id=str(staged["version_id"]))

    def set_flags(
        self, document_id: str, *, is_archived: bool | None = None, is_deleted: bool | None = None
    ) -> DocumentIndex:
        """🇺🇸 Flips `is_archived`/`is_deleted` in place — a patch-only reservation: no version, no upload.

        🇧🇷 Troca `is_archived`/`is_deleted` no lugar — uma reserva só de patch: sem versão, sem upload.
        """
        self._keyring_provider()  # 🇺🇸 lazy unlock before signing (see `list`) 🇧🇷 unlock preguiçoso antes de assinar
        body = {
            name: value
            for name, value in (("is_archived", is_archived), ("is_deleted", is_deleted))
            if value is not None
        }
        result = self._transport.post(f"{self._stream_path(document_id)}/versions", json=body)
        return DocumentIndex.model_validate(result["document"])
