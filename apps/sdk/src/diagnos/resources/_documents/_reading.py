"""🇺🇸 `_Reading`: everything about getting a document back out — list, page, fetch, decrypt, draft precedence.

🇧🇷 `_Reading`: tudo sobre trazer um documento de volta — listar, paginar, buscar, decifrar, precedência de rascunho.
"""

from __future__ import annotations

from collections.abc import Iterator

from diagnos.crypto import draft_key_id, open_draft_content, open_version_content
from diagnos.models import DocumentIndex, DocumentListItem, Page, vault_context
from diagnos.session.keyring import Keyring

from ._base import _DocumentsBase
from ._support import DATA_STREAM, DEFAULT_PAGE_SIZE, OpenedDocument, RecordT, SummaryT


class _Reading(_DocumentsBase[RecordT, SummaryT]):
    """🇺🇸 The listing and reading routes of `VersionedDocuments`.

    🇧🇷 As rotas de listagem e leitura de `VersionedDocuments`.
    """

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
        query: dict[str, str | int | bool] = {"limit": limit}
        if security_group is not None:
            query["security_group_id"] = security_group
        if include_deleted:
            query["include_deleted"] = "true"
        if cursor is not None:
            query["cursor"] = cursor
        result = self._transport.get(self._base, query=query)
        keyring = self._keyring_provider()
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

    # -- reading -------------------------------------------------------------

    def read(
        self, document_id: str, *, version_id: str | None = None, include_draft: bool = True
    ) -> OpenedDocument[RecordT, SummaryT]:
        """🇺🇸 Fetches, downloads and decrypts one document — a pinned version, or the newest content.

        Without `version_id`, the newest content wins, exactly as in the web
        app: the draft head when it is newer than the latest version, else
        the latest version. `include_draft=False` always reads the newest
        committed version.

        🇧🇷 Busca, baixa e decifra um documento — uma versão fixada, ou o conteúdo mais novo.

        Sem `version_id`, o conteúdo mais novo vence, exatamente como no app
        web: a cabeça de rascunho quando é mais nova que a versão corrente,
        senão a versão corrente. `include_draft=False` sempre lê a última
        versão confirmada.
        """
        query = self._stream_query() or {}
        if version_id is not None:
            query["version_id"] = version_id
        result = self._transport.get(f"{self._base}/{document_id}", query=query or None)
        index = DocumentIndex.model_validate(result["document"])
        dek = self._document_dek(index)
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
