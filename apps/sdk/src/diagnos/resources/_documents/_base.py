"""🇺🇸 `_DocumentsBase`: construction, URL shape and key handling shared by the read and write mixins.

`_Reading` (`_reading.py`) and `_Writing` (`_writing.py`) both need the same
document's DEK, the same `{base}[/streams/data]` URL shape, and the same
constructor state (`transport`, `keyring_provider`, …) — this is the one
place that state and those two small protocol quirks live, so `VersionedDocuments`
(`__init__.py`) is just `_Reading` and `_Writing` stitched together.

🇧🇷 `_DocumentsBase`: construção, forma de URL e chaves compartilhadas pelos mixins de leitura e escrita.

`_Reading` (`_reading.py`) e `_Writing` (`_writing.py`) precisam da mesma
DEK do documento, da mesma forma de URL `{base}[/streams/data]`, e do mesmo
estado de construtor (`transport`, `keyring_provider`, …) — este é o único
lugar onde esse estado e essas duas pequenas particularidades de protocolo
vivem, então `VersionedDocuments` (`__init__.py`) é só `_Reading` e
`_Writing` costurados juntos.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Generic

from diagnos.crypto import (
    DOCUMENT_DEK_INFO,
    INDEX_INFO,
    EntropyMixer,
    SecretBox,
    decrypt_content,
    encrypt_content,
    unwrap_key,
)
from diagnos.errors import CryptoError
from diagnos.models import DocumentIndex, DocumentListItem, ResourceKind
from diagnos.session.keyring import Keyring

from ._support import DATA_STREAM, STREAMS_BY_RESOURCE, RecordT, SummaryT

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport


class _DocumentsBase(Generic[RecordT, SummaryT]):
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

    def get_index(self, document_id: str) -> DocumentIndex:
        """🇺🇸 The index alone, discarding the `version`/`download` half of `GET {base}/{id}`.

        There is no lighter route for "just the index": this spends one
        unused presign for callers that only need metadata. Shared by
        `_Reading` (the public route) and `_Writing.update` (which needs the
        current index before staging a new version).

        🇧🇷 Só o índice, descartando a metade `version`/`download` de `GET {base}/{id}`.

        Não existe rota mais leve para "só o índice": isto gasta um presign
        não usado para quem só precisa do metadado. Compartilhado por
        `_Reading` (a rota pública) e `_Writing.update` (que precisa do
        índice corrente antes de reservar uma versão nova).
        """
        result = self._transport.get(f"{self._base}/{document_id}", query=self._stream_query())
        return DocumentIndex.model_validate(result["document"])
