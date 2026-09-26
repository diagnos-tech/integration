"""🇺🇸 `_Writing`: the two-phase write path — seal, reserve, `PUT`, commit — plus the patch-only flag flip.

🇧🇷 `_Writing`: o caminho de gravação em duas fases — selar, reservar, `PUT`, confirmar — e a troca de flag só-patch.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx

from diagnos.crypto import (
    DOCUMENT_DEK_INFO,
    SEALED_OVERHEAD_BYTES,
    SecretBox,
    generate_dek,
    seal_version_content,
    wrap_key,
)
from diagnos.errors import ConflictError, ProtocolError, VaultError
from diagnos.models import DocumentIndex

from ._base import _DocumentsBase
from ._support import (
    _SSE_C_HEADER_PREFIX,
    COMMIT_ATTEMPTS,
    COMMIT_BACKOFF_SECONDS,
    DATA_STREAM,
    STAGE_PENDING_ATTEMPTS,
    STAGE_PENDING_BACKOFF_SECONDS,
    OpenedDocument,
    RecordT,
    SummaryT,
    _is_retryable_commit_failure,
)


class _Writing(_DocumentsBase[RecordT, SummaryT]):
    """🇺🇸 The create/update/flag routes of `VersionedDocuments`.

    🇧🇷 As rotas de criar/atualizar/trocar flag de `VersionedDocuments`.
    """

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
        index = self.get_index(document_id)
        dek = self._document_dek(index)
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
        body = {
            name: value
            for name, value in (("is_archived", is_archived), ("is_deleted", is_deleted))
            if value is not None
        }
        result = self._transport.post(f"{self._stream_path(document_id)}/versions", json=body)
        return DocumentIndex.model_validate(result["document"])
