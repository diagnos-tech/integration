"""🇺🇸 `VersionedDocuments`: the one CRUD engine behind patients, exams and templates (`docs/PROTOCOL.md §8`).

`resources/patients.py` and `resources/exams.py` are thin, resource-specific
wrappers (they know the record type and the `meta` shape); every byte of
actual protocol — signing shape, encryption, upload plumbing — lives here
exactly once. A prefixed module (`_documents.py`, not `documents.py`) marks
it as internal: nothing outside `resources/` should import it directly.

There is no partial update and no delete, by design (`docs/PROTOCOL.md
§8`): changing a document always means encrypting a brand new, complete
version and committing it, and "archiving" or "deleting" one is just that
same full-version dance with a flag flipped on the stage request. Two
things make that the only sane design here, not a missing feature: the
object each version writes to R2 is a single opaque encrypted blob, so
there is no field inside it the vault could patch even if it wanted to
(only the SDK ever holds the DEK that opens it); and a versioned history
where every entry is a complete, independently-decryptable snapshot is what
lets `versions` on the index double as an audit trail, which a partial-patch
model would break the day the first patch depended on a previous one.

🇧🇷 `VersionedDocuments`: o único motor de CRUD por trás de pacientes,
exames e modelos de laudo (`docs/PROTOCOL.md §8`).

`resources/patients.py` e `resources/exams.py` são cascas finas específicas
de recurso (sabem o tipo do registro e a forma do `meta`); todo byte de
protocolo de fato — forma de assinatura, cifragem, mecânica de upload — vive
aqui uma única vez. Um módulo prefixado (`_documents.py`, não
`documents.py`) marca isto como interno: nada fora de `resources/` deveria
importar isto direto.

Não existe atualização parcial nem apagar, de propósito (`docs/PROTOCOL.md
§8`): mudar um documento sempre significa cifrar uma versão nova e
completa e confirmá-la, e "arquivar" ou "apagar" é a mesma dança de versão
completa com uma flag ligada na reserva. Duas coisas fazem disto o único
desenho são aqui, não uma funcionalidade faltando: o objeto que cada versão
escreve no R2 é um blob cifrado opaco único, então não existe campo dentro
dele que o cofre pudesse remendar mesmo que quisesse (só o SDK tem a DEK
que o abre); e um histórico versionado em que toda entrada é um retrato
completo e decifrável de forma independente é o que deixa `versions` no
índice servir de trilha de auditoria — um modelo de patch parcial quebraria
isso no dia em que o primeiro patch dependesse do anterior.
"""

from __future__ import annotations

import builtins
import json
from collections.abc import Callable, Iterator, Mapping
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel

from diagnos.crypto import (
    DEK_INFO,
    RECORD_INFO,
    EncryptedPayload,
    EntropyMixer,
    SecretBox,
    decrypt_content,
    derive_sse_c_key,
    encrypt_content,
    generate_dek,
    sse_c_headers,
    unwrap_key,
    wrap_key,
)
from diagnos.models import DocumentIndex, Page, ResourceKind
from diagnos.session.keyring import GroupKeyUnavailable, Keyring

if TYPE_CHECKING:
    from diagnos.transport.config import Settings
    from diagnos.transport.http import VaultTransport

# 🇺🇸 `list[...]` is spelled `builtins.list[...]` in this file: `VersionedDocuments`
# defines a method literally named `list`, and with `from __future__ import
# annotations` mypy resolves a bare `list` used afterwards to that method, not
# the builtin type — `builtins.list` sidesteps the name clash without giving up
# the modern generic syntax.
# 🇧🇷 `list[...]` aqui é escrito `builtins.list[...]`: `VersionedDocuments` define
# um método chamado exatamente `list`, e com `from __future__ import annotations`
# o mypy resolve um `list` usado depois para esse método, não o tipo embutido —
# `builtins.list` contorna o choque de nome sem abrir mão da sintaxe genérica moderna.
RecordT = TypeVar("RecordT", bound=BaseModel)

# 🇺🇸 §13: list pages cap at 200; 50 mirrors the vault's own web-client
# default, comfortable for a REPL without a caller ever having to think
# about pagination for a small workspace.
# 🇧🇷 §13: páginas de lista têm teto de 200; 50 espelha o padrão do próprio
# client web do cofre, confortável num REPL sem quem chama ter que pensar em
# paginação para um workspace pequeno.
DEFAULT_PAGE_SIZE = 50


def coerce_record(model: type[RecordT], value: RecordT | Mapping[str, Any]) -> RecordT:
    """🇺🇸 Accepts a model instance as-is, or validates a plain `dict` into one.

    The one place `Patients`/`Exams` let a caller pass `{"legal_name": ...}`
    instead of constructing `PatientRecord(...)` first — good REPL ergonomics
    without weakening validation, since a `dict` still goes through the same
    pydantic model either way.

    🇧🇷 Aceita uma instância do modelo como está, ou valida um `dict` puro nela.

    O único lugar onde `Patients`/`Exams` deixam quem chama passar
    `{"legal_name": ...}` em vez de construir `PatientRecord(...)` antes —
    boa ergonomia de REPL sem enfraquecer a validação, já que um `dict`
    passa pelo mesmo modelo pydantic de qualquer jeito.
    """
    return value if isinstance(value, model) else model.model_validate(value)


class VersionedDocuments(Generic[RecordT]):
    """🇺🇸 CRUD over one resource (`patients`/`exams`/`templates`) of one workspace, fully generic over the record type.

    🇧🇷 CRUD sobre um recurso (`patients`/`exams`/`templates`) de um workspace, genérico no tipo do registro.
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
        settings: Settings,
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
        self._settings = settings
        self._base = f"/api/external/v1/workspaces/{workspace_id}/{resource}"

    # -- listing -----------------------------------------------------------

    def list(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[DocumentIndex]:
        """🇺🇸 One page of the index (`GET {base}`, `docs/PROTOCOL.md §8`).

        🇧🇷 Uma página do índice (`GET {base}`, `docs/PROTOCOL.md §8`).
        """
        query: dict[str, str | int | bool] = {"limit": limit}
        if security_group is not None:
            query["security_group_id"] = security_group
        if include_deleted:
            query["include_deleted"] = True
        if cursor is not None:
            query["cursor"] = cursor
        result = self._transport.get(self._base, query=query)
        items = [DocumentIndex.model_validate(item) for item in result["items"]]
        return Page(items=items, next_cursor=result.get("next_cursor"))

    def iter_all(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[DocumentIndex]:
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

        There is no lighter endpoint for "just the index" (`docs/PROTOCOL.md
        §8` always answers with a fresh signed download URL attached) — this
        trades one wasted presign for callers that only need metadata
        (`update`/`archive`/`unarchive`/`delete` all call this to find the
        current `encrypted_keys`).

        🇧🇷 Só o índice, descartando a metade `version`/`download` de `GET {base}/{id}`.

        Não existe uma rota mais leve para "só o índice" (`docs/PROTOCOL.md
        §8` sempre responde com uma URL de download assinada nova junto) —
        isto troca um presign desperdiçado por quem só precisa do metadado
        (`update`/`archive`/`unarchive`/`delete` chamam isto para achar o
        `encrypted_keys` atual).
        """
        result = self._transport.get(f"{self._base}/{document_id}")
        return DocumentIndex.model_validate(result["document"])

    # -- reading -------------------------------------------------------------

    def _select_group(self, index: DocumentIndex) -> str:
        """🇺🇸 The first security group in `index.security_groups` this keyring holds a DEK for.

        🇧🇷 O primeiro security group de `index.security_groups` para o qual este keyring tem uma DEK.
        """
        available = set(self._keyring_provider().security_group_ids)
        for security_group_id in index.security_groups:
            if security_group_id in available:
                return security_group_id
        raise GroupKeyUnavailable(
            f"🇺🇸 no DEK for any of {index.security_groups!r} was handed to this enrollment; "
            f"cannot open document {index.document_id!r}. "
            f"🇧🇷 nenhuma DEK de {index.security_groups!r} foi entregue a este enrollment; "
            f"não é possível abrir o documento {index.document_id!r}."
        )

    def _unwrap_document_dek(self, index: DocumentIndex) -> SecretBox:
        """🇺🇸 Picks an available security group and unwraps that document's DEK from it.

        🇧🇷 Escolhe um security group disponível e desembrulha a DEK do documento a partir dele.
        """
        security_group_id = self._select_group(index)
        group_dek = self._keyring_provider().group_key(security_group_id)
        encrypted = index.encrypted_keys[security_group_id]
        return unwrap_key(group_dek, encrypted, DEK_INFO[self._resource])

    def _sse_headers(self, doc_dek: SecretBox) -> dict[str, str]:
        """🇺🇸 The three SSE-C headers when `settings.sse_c` is on, else nothing (`docs/PROTOCOL.md §10`).

        🇧🇷 Os três headers de SSE-C quando `settings.sse_c` está ligado, senão nada (`docs/PROTOCOL.md §10`).
        """
        if not self._settings.sse_c:
            return {}
        return sse_c_headers(derive_sse_c_key(doc_dek))

    def read(self, document_id: str, *, version_id: str | None = None) -> tuple[DocumentIndex, RecordT]:
        """🇺🇸 Fetches the index, downloads the encrypted object and decrypts it into `record_model`.

        🇧🇷 Busca o índice, baixa o objeto cifrado e o decifra em `record_model`.
        """
        query = {"version_id": version_id} if version_id is not None else None
        result = self._transport.get(f"{self._base}/{document_id}", query=query)
        index = DocumentIndex.model_validate(result["document"])
        doc_dek = self._unwrap_document_dek(index)
        raw = self._transport.download_bytes(result["download"]["url"], headers=self._sse_headers(doc_dek))
        payload = EncryptedPayload.from_dict(json.loads(raw))
        plaintext = decrypt_content(doc_dek, payload, RECORD_INFO[self._resource])
        record = self._record_model.model_validate_json(plaintext)
        return index, record

    # -- writing -------------------------------------------------------------

    def _encrypt_record_body(self, doc_dek: SecretBox, record: RecordT) -> bytes:
        """🇺🇸 Serializes `record` and encrypts it into the exact `{salt,nonce,ciphertext}` JSON object body.

        `exclude_none=True`: an absent optional field and one explicitly set
        to `None` are the same fact for every record in this protocol (there
        is no partial-update semantics that would make the distinction
        matter, see the module docstring), so there is no reason to spend
        bytes — cifrados, at that — writing `null`s.

        🇧🇷 Serializa `record` e cifra no corpo JSON `{salt,nonce,ciphertext}` exato.

        `exclude_none=True`: um campo opcional ausente e um explicitamente
        `None` são o mesmo fato para todo registro deste protocolo (não há
        semântica de atualização parcial que faria a distinção importar, ver
        a docstring do módulo), então não há motivo para gastar bytes —
        cifrados, ainda por cima — escrevendo `null`s.
        """
        plaintext = record.model_dump_json(exclude_none=True).encode("utf-8")
        payload = encrypt_content(doc_dek, plaintext, RECORD_INFO[self._resource])
        return json.dumps(payload.to_dict()).encode("utf-8")

    def _put_object(self, upload: Mapping[str, Any], doc_dek: SecretBox, body: bytes) -> None:
        """🇺🇸 `PUT`s `body` to `upload["url"]` with an exact `content-length`, plus SSE-C if enabled.

        🇧🇷 Faz `PUT` de `body` em `upload["url"]` com `content-length` exato, mais SSE-C se ligado.
        """
        headers = {"content-length": str(len(body)), **self._sse_headers(doc_dek)}
        self._transport.upload_bytes(upload["url"], body, headers)

    def create(
        self,
        record: RecordT,
        *,
        security_groups: builtins.list[str],
        meta: dict[str, Any] | None = None,
    ) -> DocumentIndex:
        """🇺🇸 Generates a fresh DEK, wraps it per group, encrypts `record`, then stage → PUT → commit.

        🇧🇷 Gera uma DEK nova, embrulha por grupo, cifra `record`, depois reserva → PUT → confirma.
        """
        keyring = self._keyring_provider()
        doc_dek = generate_dek(self._entropy)
        body = self._encrypt_record_body(doc_dek, record)
        dek_info = DEK_INFO[self._resource]
        encrypted_keys = {
            security_group_id: wrap_key(keyring.group_key(security_group_id), doc_dek, dek_info).to_dict()
            for security_group_id in security_groups
        }
        request_body: dict[str, Any] = {
            "security_groups": list(security_groups),
            "encrypted_keys": encrypted_keys,
            "content_length": len(body),
        }
        if meta:
            request_body["meta"] = meta
        result = self._transport.post(self._base, json=request_body)
        document = DocumentIndex.model_validate(result["document"])
        self._put_object(result["upload"], doc_dek, body)
        committed = self._transport.post(f"{self._base}/{document.document_id}/versions/{result['version_id']}/commit")
        return DocumentIndex.model_validate(committed["document"])

    def update(
        self,
        document_id: str,
        record: RecordT,
        *,
        meta: dict[str, Any] | None = None,
        is_archived: bool | None = None,
        is_deleted: bool | None = None,
    ) -> DocumentIndex:
        """🇺🇸 Reuses the document's existing DEK (found via the current index) to encrypt a brand new version.

        🇧🇷 Reusa a DEK existente do documento (achada pelo índice atual) para cifrar uma versão nova.
        """
        index = self.get_index(document_id)
        doc_dek = self._unwrap_document_dek(index)
        body = self._encrypt_record_body(doc_dek, record)
        request_body: dict[str, Any] = {"content_length": len(body)}
        if meta:
            request_body["meta"] = meta
        if is_archived is not None:
            request_body["is_archived"] = is_archived
        if is_deleted is not None:
            request_body["is_deleted"] = is_deleted
        result = self._transport.post(f"{self._base}/{document_id}/versions", json=request_body)
        self._put_object(result["upload"], doc_dek, body)
        committed = self._transport.post(f"{self._base}/{document_id}/versions/{result['version_id']}/commit")
        return DocumentIndex.model_validate(committed["document"])

    def _reupload_with_flag(
        self,
        document_id: str,
        *,
        is_archived: bool | None = None,
        is_deleted: bool | None = None,
    ) -> DocumentIndex:
        """🇺🇸 Archive/unarchive/delete are all "read the current record, write it back with one flag flipped".

        🇧🇷 Arquivar/desarquivar/apagar são todos "ler o registro atual, reescrever com uma flag trocada".
        """
        _index, record = self.read(document_id)
        return self.update(document_id, record, is_archived=is_archived, is_deleted=is_deleted)

    def archive(self, document_id: str) -> DocumentIndex:
        """🇺🇸 Sets `is_archived=True` on a new version. 🇧🇷 Liga `is_archived=True` numa versão nova."""
        return self._reupload_with_flag(document_id, is_archived=True)

    def unarchive(self, document_id: str) -> DocumentIndex:
        """🇺🇸 Sets `is_archived=False` on a new version. 🇧🇷 Desliga `is_archived` numa versão nova."""
        return self._reupload_with_flag(document_id, is_archived=False)

    def delete(self, document_id: str) -> DocumentIndex:
        """🇺🇸 Sets `is_deleted=True` on a new version — never a hard delete (`docs/PROTOCOL.md §8`).

        🇧🇷 Liga `is_deleted=True` numa versão nova — nunca um apagar de verdade (`docs/PROTOCOL.md §8`).
        """
        return self._reupload_with_flag(document_id, is_deleted=True)
