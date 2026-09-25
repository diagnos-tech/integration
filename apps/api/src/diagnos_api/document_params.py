"""🇺🇸 Query parameters shared by `/v1/patients` and `/v1/exams`, and the list-summary rule.

List responses: sealed summaries leave the process only when the caller
asks (`?summary=true`).

The SDK always opens each row's `encrypted_index` (it costs one AES-GCM per
row and no extra request); what this facade decides is whether names and
titles cross the network. Anonymous rows by default is the same rule the
CLI follows, and it keeps a list endpoint polled by a dashboard from
shipping a whole workspace's names on every refresh.

🇧🇷 Parâmetros de query comuns a `/v1/patients` e `/v1/exams`, e a regra de resumo nas listas.

Respostas de lista: resumos selados só saem do processo quando quem chama
pede (`?summary=true`).

O SDK sempre abre o `encrypted_index` de cada linha (custa um AES-GCM por
linha e nenhuma requisição a mais); o que esta fachada decide é se nomes e
títulos atravessam a rede. Linhas anônimas por padrão é a mesma regra da
CLI, e impede que um endpoint de lista consultado por um painel mande os
nomes de um workspace inteiro a cada atualização.
"""

from __future__ import annotations

from typing import TypeVar

from diagnos import DocumentListItem, Page
from pydantic import BaseModel

SummaryT = TypeVar("SummaryT", bound=BaseModel)

DRAFT_QUERY_HELP = (
    "🇺🇸 Read the web editor's draft when it is newer than the latest version (the web app's rule). "
    "🇧🇷 Lê o rascunho do editor web quando é mais novo que a versão corrente (a regra do app web)."
)
SUMMARY_QUERY_HELP = (
    "🇺🇸 Include each row's decrypted summary (names/tags, or title/modality/date). "
    "🇧🇷 Inclui o resumo decifrado de cada linha (nomes/tags, ou título/modalidade/data)."
)


def with_summaries(page: Page[DocumentListItem[SummaryT]], *, include: bool) -> Page[DocumentListItem[SummaryT]]:
    """🇺🇸 `page` as-is when `include`, else with every `summary` set to `null`.

    🇧🇷 `page` como veio quando `include`, senão com todo `summary` em `null`.
    """
    if include:
        return page
    items = [item.model_copy(update={"summary": None}) for item in page.items]
    return Page(items=items, next_cursor=page.next_cursor)
