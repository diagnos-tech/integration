"""🇺🇸 `/v1/drives/{sg}/…` — a thin HTTP face over `vault.drives` (`apps/sdk/src/diagnos/resources/drives/`).

A "drive" is a security group; `sg` in every path below is that group's id.
The vault addresses a node by its id alone, so a read also checks that the
node really lives in `sg` — a node from another group answers 404, exactly
like one that does not exist, instead of being served under the wrong path.
Handlers stay plain `def` for the same reason as `routers/patients.py`:
`Drive.*` blocks on network I/O and on local encryption work, so Starlette's
thread pool — not the event loop — is where it belongs.

Uploads pass through a temporary file instead of holding a whole file in
RAM: `Drive.upload` already does this itself for any source that is not a
path or `bytes` (`resources/drives/_source.py`), so an `UploadFile`'s spooled
file gets a second, redundant spool — a real cost, paid once per upload, in
exchange for never needing to know a file's size before the multipart body
finishes parsing. Downloads never touch disk: `iter_download` decrypts
lazily, one chunk at a time, and `StreamingResponse` forwards each chunk as
it is produced — bounded by one chunk of RAM, first bytes out before the last
ones arrive from the vault.

🇧🇷 `/v1/drives/{sg}/…` — uma face HTTP fina sobre `vault.drives`
(`apps/sdk/src/diagnos/resources/drives/`).

Um "drive" é um security group; `sg` em todo path abaixo é o id desse
grupo. O cofre endereça um nó só pelo id, então uma leitura também confere
que o nó mora mesmo em `sg` — um nó de outro grupo responde 404, igual a um
que não existe, em vez de ser servido sob o path errado. Os handlers ficam
`def` puro pela mesma razão de `routers/patients.py`: `Drive.*` bloqueia em
I/O de rede e em trabalho local de cifragem, então o lugar certo é a thread
pool do Starlette — não o event loop.

Upload passa por um arquivo temporário em vez de segurar um arquivo
inteiro na RAM: `Drive.upload` já faz isso sozinho para qualquer fonte que
não seja path ou `bytes` (`resources/drives/_source.py`), então o arquivo já
derramado de um `UploadFile` sofre um segundo derramamento — um custo real,
pago uma vez por upload, em troca de nunca precisar saber o tamanho de um
arquivo antes do corpo multipart terminar de ser interpretado. Download
nunca toca o disco: `iter_download` decifra de forma preguiçosa, um pedaço
por vez, e o `StreamingResponse` repassa cada pedaço conforme é produzido —
limitado a um pedaço de RAM, primeiros bytes saindo antes de os últimos
chegarem do cofre.
"""

from __future__ import annotations

import re
from typing import Annotated
from urllib.parse import quote

from diagnos import Diagnos, Drive, DriveNode, GroupKeyUnavailable, NotFoundError, Page
from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile
from fastapi.responses import StreamingResponse

from diagnos_api.deps import get_vault
from diagnos_api.document_params import CURSOR_QUERY_HELP, LIMIT_QUERY_HELP
from diagnos_api.errors import ERROR_RESPONSES
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.schemas import FolderCreated, FolderCreateRequest, NodeView

router = APIRouter(prefix="/v1/drives/{sg}", tags=["drives"], responses=ERROR_RESPONSES)

SecurityGroup = Annotated[str, Path(description="🇺🇸 The security group (the drive). 🇧🇷 O security group (o drive).")]
NodeId = Annotated[str, Path(description="🇺🇸 The file's node id. 🇧🇷 O id do nó do arquivo.")]

# 🇺🇸 CR/LF would let a crafted decrypted filename inject a second header
# into the response; quotes and control bytes would break the
# `filename="..."` value. All are replaced, never rejected outright, because
# a node's name is data a caller supplied when uploading, not something this
# endpoint should refuse to serve over.
# 🇧🇷 CR/LF deixariam um nome decifrado forjado injetar um segundo header na
# resposta; aspas e bytes de controle quebrariam o valor de
# `filename="..."`. Todos são substituídos, nunca rejeitados de vez, porque
# o nome de um nó é dado que quem chamou forneceu no upload, não algo que
# este endpoint deva recusar a servir.
_UNSAFE_FILENAME_CHARS = re.compile(r'["\\\x00-\x1f\x7f]')

_FALLBACK_NAME = "arquivo"


def _content_disposition(name: str) -> str:
    """🇺🇸 A `Content-Disposition` for a decrypted name: its last path segment, header-safe, non-ASCII kept.

    The web app seals a relative path as the name (`exams/2024/scan.dcm`);
    a browser saving `filename="exams/2024/scan.dcm"` would either reject
    it or flatten it unpredictably, so only the last segment is offered.

    🇧🇷 Um `Content-Disposition` para um nome decifrado: o último segmento do caminho, seguro para header,
    não-ASCII mantido.

    O app web sela um caminho relativo como nome (`exams/2024/scan.dcm`);
    um navegador salvando `filename="exams/2024/scan.dcm"` recusaria ou
    achataria de forma imprevisível, então só o último segmento é oferecido.
    """
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    safe = _UNSAFE_FILENAME_CHARS.sub("_", base).strip()
    if safe in ("", ".", ".."):
        safe = _FALLBACK_NAME
    ascii_fallback = safe.encode("ascii", "replace").decode("ascii")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(safe)}"


def _listed_name(drive: Drive, node: DriveNode) -> str | None:
    """🇺🇸 A listed node's name, or `null` when this process holds no key for its group — like document summaries.

    🇧🇷 O nome de um nó listado, ou `null` quando este processo não tem a chave do grupo — como os resumos de documento.
    """
    try:
        return drive.name_of(node)
    except GroupKeyUnavailable:
        return None


def _node_in_group(vault: Diagnos, sg: str, node_id: str) -> DriveNode:
    """🇺🇸 The node, or the vault's own 404 when it does not exist or belongs to another group.

    🇧🇷 O nó, ou o próprio 404 do cofre quando ele não existe ou pertence a outro grupo.
    """
    node = vault.drives.get(node_id)
    if node.security_group_id != sg:
        raise NotFoundError(code="DriveNodeNotFound", message=f"no node {node_id!r} in {sg!r}", status=404)
    return node


@router.get(
    "/nodes",
    response_model=Page[NodeView],
    summary="🇺🇸 List drive nodes 🇧🇷 Lista nós do drive",
    description="🇺🇸 One page of files and folders in security group `sg`, each with its name decrypted (`null` when "
    "this process holds no key for the group). "
    "🇧🇷 Uma página de arquivos e pastas do security group `sg`, cada um com o nome decifrado (`null` quando este "
    "processo não tem a chave do grupo).",
)
def list_nodes(
    sg: SecurityGroup,
    exam_id: str | None = Query(None, description="🇺🇸 Only files linked to this exam. 🇧🇷 Só arquivos deste exame."),
    parent_id: str | None = Query(None, description="🇺🇸 Folder node id. 🇧🇷 Id do nó da pasta."),
    include_pending: bool = Query(
        False, description="🇺🇸 Include uploads not finished yet. 🇧🇷 Inclui uploads ainda não terminados."
    ),
    limit: int = Query(50, ge=1, le=200, description=LIMIT_QUERY_HELP),
    cursor: str | None = Query(None, description=CURSOR_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[NodeView]:
    """🇺🇸 Lists via `Drive.list`, then decrypts each node's name with `Drive.name_of`.

    🇧🇷 Lista via `Drive.list`, depois decifra o nome de cada nó com `Drive.name_of`.
    """
    drive = vault.drives.drive(sg)
    page = drive.list(exam_id=exam_id, parent_id=parent_id, include_pending=include_pending, limit=limit, cursor=cursor)
    items = [NodeView(node=node, name=_listed_name(drive, node)) for node in page.items]
    return Page(items=items, next_cursor=page.next_cursor)


@router.get(
    "/nodes/{node_id}",
    response_model=NodeView,
    summary="🇺🇸 Get one drive node 🇧🇷 Busca um nó do drive",
    description="🇺🇸 One ready file's metadata plus its decrypted name. "
    "🇧🇷 O metadado de um arquivo pronto mais o nome decifrado.",
)
def get_node(
    sg: SecurityGroup,
    node_id: NodeId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> NodeView:
    """🇺🇸 Delegates to `Drives.get`/`Drives.name_of`. 🇧🇷 Delega para `Drives.get`/`Drives.name_of`."""
    node = _node_in_group(vault, sg, node_id)
    return NodeView(node=node, name=vault.drives.name_of(node))


@router.post(
    "/nodes",
    response_model=DriveNode,
    status_code=201,
    summary="🇺🇸 Upload a file 🇧🇷 Sobe um arquivo",
    description="🇺🇸 Encrypts and uploads `file` into security group `sg`, optionally inside folder `parent_id` "
    "and linked to `exam_id`; single `PUT` or multipart is chosen by the SDK from its size. The whole multipart "
    "body is buffered (`python-multipart`'s `SpooledTemporaryFile`, 1 MiB in RAM before it spills to disk) "
    "before this handler even runs, so request size is what bounds memory, not this endpoint's own logic. "
    "🇧🇷 Cifra e sobe `file` no security group `sg`, opcionalmente dentro da pasta `parent_id` e ligado a "
    "`exam_id`; `PUT` único ou multipart é escolhido pelo SDK a partir do tamanho. O corpo multipart inteiro é "
    "bufferizado (`SpooledTemporaryFile` do `python-multipart`, 1 MiB em RAM antes de derramar em disco) antes "
    "deste handler sequer rodar, então é o tamanho da requisição que limita a memória, não a lógica deste "
    "endpoint.",
)
def upload_node(
    sg: SecurityGroup,
    file: UploadFile = File(...),
    exam_id: str | None = Form(None),
    parent_id: str | None = Form(None),
    mime_type: str | None = Form(None),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DriveNode:
    """🇺🇸 Passes the already-spooled `UploadFile.file` straight to `Drive.upload`.

    🇧🇷 Passa o `UploadFile.file` já derramado direto para `Drive.upload`.
    """
    drive = vault.drives.drive(sg)
    file.file.seek(0)
    return drive.upload(
        file.file,
        name=file.filename or _FALLBACK_NAME,
        mime_type=mime_type or file.content_type,
        exam_id=exam_id,
        parent_id=parent_id,
    )


@router.post(
    "/folders",
    response_model=FolderCreated,
    status_code=201,
    summary="🇺🇸 Create a folder 🇧🇷 Cria uma pasta",
    description="🇺🇸 Creates a folder in security group `sg` (its name sealed like a file's); pass the returned "
    "`node_id` as `parent_id` when uploading. "
    "🇧🇷 Cria uma pasta no security group `sg` (nome selado como o de um arquivo); passe o `node_id` devolvido "
    "como `parent_id` ao subir.",
)
def create_folder(
    sg: SecurityGroup,
    body: FolderCreateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> FolderCreated:
    """🇺🇸 Delegates to `Drive.create_folder`. 🇧🇷 Delega para `Drive.create_folder`."""
    node_id = vault.drives.drive(sg).create_folder(body.name, parent_id=body.parent_id)
    return FolderCreated(node_id=node_id)


@router.get(
    "/nodes/{node_id}/content",
    summary="🇺🇸 Download decrypted content 🇧🇷 Baixa o conteúdo decifrado",
    description="🇺🇸 Streams the decrypted bytes of one file, with its decrypted (sanitized) name in "
    "`Content-Disposition`. "
    "🇧🇷 Transmite os bytes decifrados de um arquivo, com o nome decifrado (higienizado) em "
    "`Content-Disposition`.",
)
def download_node_content(
    sg: SecurityGroup,
    node_id: NodeId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> StreamingResponse:
    """🇺🇸 Streams `Drives.iter_download` straight into the response — no temp file, one chunk in RAM.

    🇧🇷 Transmite `Drives.iter_download` direto na resposta — sem arquivo temporário, um pedaço na RAM.
    """
    drives = vault.drives
    node = _node_in_group(vault, sg, node_id)
    headers = {"content-disposition": _content_disposition(drives.name_of(node) or node_id)}
    media_type = node.mime_type or "application/octet-stream"
    return StreamingResponse(drives.iter_download(node_id), media_type=media_type, headers=headers)
