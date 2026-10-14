"""`_Reading`: everything about getting a document back out (list, page, fetch, decrypt, draft precedence)."""

from __future__ import annotations

from collections.abc import Iterator

from diagnos.crypto import draft_key_id, open_draft_content, open_version_content
from diagnos.models import DocumentIndex, DocumentListItem, Page, vault_context
from diagnos.session.keyring import Keyring

from ._base import _DocumentsBase
from ._support import DATA_STREAM, DEFAULT_PAGE_SIZE, OpenedDocument, RecordT, SummaryT


class _Reading(_DocumentsBase[RecordT, SummaryT]):
    """The listing and reading routes of `VersionedDocuments`."""

    # -- listing -------------------------------------------------------------

    def list(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[DocumentListItem[SummaryT]]:
        """Fetch one page of the index (`GET {base}`), each row with its summary already decrypted.

        No version is downloaded: the summary comes from `encrypted_index`,
        which is what lets the web app render a list of names offline. A row
        whose group key this session does not hold keeps `summary=None`
        instead of failing the whole page.

        Args:
            security_group: Only list documents of this security group.
            include_deleted: Whether to include documents in the trash.
            limit: The page size (the vault caps it at 200).
            cursor: The `next_cursor` of the previous page; `None` for the first page.

        Returns:
            The page of rows and the cursor for the next one.
        """
        # The keyring first: asking for it is what unlocks lazily (`Diagnos._keyring_provider`), and a
        # signed request cannot go out before there is a session, so `list()` may be a program's first call.
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
        """Build one list row: the index plus its summary when this session can open it."""
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
        """Walk every page by following `next_cursor` until it is `None`.

        Args:
            security_group: Only list documents of this security group.
            include_deleted: Whether to include documents in the trash.
            limit: The page size used for each request.

        Yields:
            Every row, in the order the vault returns them.
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
        """Fetch, download and decrypt one document: a pinned version, or the newest content.

        Without `version_id`, the newest content wins, exactly as in the web
        app: the draft head when it is newer than the latest version, else
        the latest version. `include_draft=False` always reads the newest
        committed version.

        Args:
            document_id: The document to read.
            version_id: Read this committed version instead of the newest content.
            include_draft: Whether the draft head may win over the latest version. Ignored with `version_id`.

        Returns:
            The index, decrypted record and summary, and where the record came from.

        Raises:
            NotFoundError: If the document or version does not exist.
            GroupKeyUnavailable: If this session holds no DEK for the document's security group.
            CryptoError: If the document has no DEK sealed for its own group, or a payload does not open.
        """
        keyring = self._keyring_provider()  # lazy unlock first (see `list`)
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
        """Validate decrypted plaintext, tolerating fields the SDK does not model yet."""
        return self._record_model.model_validate_json(plaintext, context=vault_context())
