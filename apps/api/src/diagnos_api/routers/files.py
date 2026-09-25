"""🇺🇸 `/v1/drives/{sg}/nodes` — a thin HTTP face over `vault.drives` (`apps/sdk/src/diagnos/resources/drives.py`).

A "drive" is a security group; `sg` in every path below is that group's id.
Handlers stay plain `def` for the same reason as `routers/patients.py`:
`Drive.*` blocks on network I/O and on local AES-GCM work, so Starlette's
thread pool — not the event loop — is where it belongs.

Uploads pass through a temporary file instead of holding a whole file in
RAM: `Drive.upload` already does this itself for any source that is not a
path or `bytes` (`resources/drives/_source.py`), so an `UploadFile`'s spooled
file gets a second, redundant spool — a real cost, paid once per upload, in
exchange for never needing to know a file's size before the multipart body
finishes parsing. Downloads never touch disk: `Drive.iter_download` decrypts
lazily, one chunk at a time, and `StreamingResponse` forwards each chunk as
it is produced — bounded by one chunk of RAM, first bytes out before the last
ones arrive from the vault.

🇧🇷 `/v1/drives/{sg}/nodes` — uma face HTTP fina sobre `vault.drives`
(`apps/sdk/src/diagnos/resources/drives.py`).

Um "drive" é um security group; `sg` em todo path abaixo é o id desse
grupo. Os handlers ficam `def` puro pela mesma razão de
`routers/patients.py`: `Drive.*` bloqueia em I/O de rede e em trabalho
local de AES-GCM, então o lugar certo é a thread pool do Starlette — não o
event loop.

Upload passa por um arquivo temporário em vez de segurar um arquivo
inteiro na RAM: `Drive.upload` já faz isso sozinho para qualquer fonte que
não seja path ou `bytes` (`resources/drives/_source.py`), então o arquivo já
derramado de um `UploadFile` sofre um segundo derramamento — um custo real,
pago uma vez por upload, em troca de nunca precisar saber o tamanho de um
arquivo antes do corpo multipart terminar de ser interpretado. Download
nunca toca o disco: `Drive.iter_download` decifra de forma preguiçosa, um
pedaço por vez, e o `StreamingResponse` repassa cada pedaço conforme é
produzido — limitado a um pedaço de RAM, primeiros bytes saindo antes de os
últimos chegarem do cofre.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from diagnos import Diagnos, DriveNode, Page
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from diagnos_api.deps import get_vault
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.schemas import NodeView

router = APIRouter(prefix="/v1/drives/{sg}/nodes", tags=["drives"])

# 🇺🇸 CR/LF would let a crafted decrypted filename inject a second header
# into the response; quotes and slashes would break the `filename="..."`
# value or read as a path. All four are replaced, never rejected outright,
# because a node's name is data a caller supplied when uploading, not
# something this endpoint should refuse to serve over.
# 🇧🇷 CR/LF deixariam um nome decifrado forjado injetar um segundo header na
# resposta; aspas e barras quebrariam o valor de `filename="..."` ou seriam
# lidas como path. As quatro são substituídas, nunca rejeitadas de vez,
# porque o nome de um nó é dado que quem chamou forneceu no upload, não algo
# que este endpoint deva recusar a servir.
_UNSAFE_FILENAME_CHARS = re.compile(r'[\r\n"/\\\x00-\x1f]')


def _content_disposition(name: str) -> str:
    """🇺🇸 A `Content-Disposition` header safe against header injection and non-ASCII names alike.

    🇧🇷 Um header `Content-Disposition` seguro tanto contra injeção de header quanto nomes não-ASCII.
    """
    safe = _UNSAFE_FILENAME_CHARS.sub("_", name).strip() or "arquivo"
    ascii_fallback = safe.encode("ascii", "replace").decode("ascii")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(safe)}"


@router.get(
    "",
    response_model=Page[NodeView],
    summary="List drive nodes · Lista nós do drive",
    description="🇺🇸 One page of nodes in security group `sg`, each with its name decrypted. "
    "🇧🇷 Uma página de nós do security group `sg`, cada um com o nome decifrado.",
)
def list_nodes(
    sg: str,
    exam_id: str | None = None,
    include_pending: bool = False,
    limit: int = 50,
    cursor: str | None = None,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[NodeView]:
    """🇺🇸 Lists via `Drive.list`, then decrypts each node's name with `Drive.name_of`.

    🇧🇷 Lista via `Drive.list`, depois decifra o nome de cada nó com `Drive.name_of`.
    """
    drive = vault.drives.drive(sg)
    page = drive.list(exam_id=exam_id, include_pending=include_pending, limit=limit, cursor=cursor)
    items = [NodeView(node=node, name=drive.name_of(node)) for node in page.items]
    return Page(items=items, next_cursor=page.next_cursor)


@router.get(
    "/{node_id}",
    response_model=NodeView,
    summary="Get one drive node · Busca um nó do drive",
    description="🇺🇸 One node's index plus its decrypted name. 🇧🇷 O índice de um nó mais o nome decifrado.",
)
def get_node(
    sg: str,
    node_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> NodeView:
    """🇺🇸 Delegates to `Drive.get`/`Drive.name_of`. 🇧🇷 Delega para `Drive.get`/`Drive.name_of`."""
    drive = vault.drives.drive(sg)
    node = drive.get(node_id)
    return NodeView(node=node, name=drive.name_of(node))


@router.post(
    "",
    response_model=DriveNode,
    status_code=201,
    summary="Upload a file · Sobe um arquivo",
    description="🇺🇸 Encrypts and uploads `file` into security group `sg`; single-PUT or multipart is chosen "
    "by the SDK from its size. The whole multipart body is buffered (`python-multipart`'s "
    "`SpooledTemporaryFile`, default 1 MiB in RAM before it spills to disk) before this handler even "
    "runs, so request size is what bounds memory, not this endpoint's own logic. "
    "🇧🇷 Cifra e sobe `file` no security group `sg`; PUT único ou multipart é escolhido pelo SDK a "
    "partir do tamanho. O corpo multipart inteiro é bufferizado (`SpooledTemporaryFile` do "
    "`python-multipart`, 1 MiB em RAM por padrão antes de derramar em disco) antes deste handler "
    "sequer rodar, então é o tamanho da requisição que limita a memória, não a lógica deste endpoint.",
)
def upload_node(
    sg: str,
    file: UploadFile = File(...),
    exam_id: str | None = Form(None),
    mime_type: str | None = Form(None),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DriveNode:
    """🇺🇸 Passes the already-spooled `UploadFile.file` straight to `Drive.upload`.

    🇧🇷 Passa o `UploadFile.file` já derramado direto para `Drive.upload`.
    """
    drive = vault.drives.drive(sg)
    file.file.seek(0)
    return drive.upload(file.file, name=file.filename, mime_type=mime_type or file.content_type, exam_id=exam_id)


@router.get(
    "/{node_id}/content",
    summary="Download decrypted content · Baixa o conteúdo decifrado",
    description="🇺🇸 Streams the decrypted bytes of one node, with its decrypted (sanitized) name in "
    "`Content-Disposition`. "
    "🇧🇷 Transmite os bytes decifrados de um nó, com o nome decifrado (higienizado) em "
    "`Content-Disposition`.",
)
def download_node_content(
    sg: str,
    node_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> StreamingResponse:
    """🇺🇸 Streams `Drive.iter_download` straight into the response — no temp file, one chunk in RAM.

    🇧🇷 Transmite `Drive.iter_download` direto na resposta — sem arquivo temporário, um pedaço na RAM.
    """
    drive = vault.drives.drive(sg)
    node = drive.get(node_id)
    name = drive.name_of(node) or node_id

    headers = {"content-disposition": _content_disposition(name)}
    media_type = node.mime_type or "application/octet-stream"
    return StreamingResponse(drive.iter_download(node_id), media_type=media_type, headers=headers)
