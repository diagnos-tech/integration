"""Query parameters shared by `/v1/patients` and `/v1/exams`, and the list-summary rule.

List responses: sealed summaries leave the process only when the caller asks (`?summary=true`).

The SDK always opens each row's `encrypted_index` (one AES-GCM per row, no extra request); what this facade decides is
whether names and titles cross the network. Anonymous rows by default is the same rule the CLI follows, and it keeps a
list endpoint that a dashboard polls from shipping a whole workspace's names on every refresh.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from diagnos import DocumentListItem, Page

SummaryT = TypeVar("SummaryT", bound=BaseModel)

GROUP_QUERY_HELP = "Only this security group (default: every group this process may list)."
DELETED_QUERY_HELP = "Include documents in the trash."
LIMIT_QUERY_HELP = "Page size, 1–200."
CURSOR_QUERY_HELP = "The `next_cursor` of the previous page."
VERSION_QUERY_HELP = "Read this committed version instead of the newest content."
DRAFT_QUERY_HELP = "Read the web editor's draft when it is newer than the latest version (the web app's rule)."
SUMMARY_QUERY_HELP = "Include each row's decrypted summary (names/tags, or title/modality/date)."


def with_summaries(page: Page[DocumentListItem[SummaryT]], *, include: bool) -> Page[DocumentListItem[SummaryT]]:
    """Returns `page` unchanged when `include` is true, else a copy with every `summary` set to `null`.

    Args:
        page: A page of list rows, as the SDK returned it.
        include: Whether the caller asked for the decrypted summaries (`?summary=true`).

    Returns:
        `page` itself when `include`, otherwise a new `Page` with the same cursor and anonymous rows.
    """
    if include:
        return page
    items = [item.model_copy(update={"summary": None}) for item in page.items]
    return Page(items=items, next_cursor=page.next_cursor)
