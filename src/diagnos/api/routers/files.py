"""`/v1/drives/{sg}/…`: a thin HTTP face over `vault.drives` (`apps/sdk/src/diagnos/resources/drives/`).

A "drive" is a security group, and `sg` in every path below is that group's id. The vault addresses a node by its id
alone, so a read also checks that the node really lives in `sg`: a node from another group answers 404, exactly like
one that does not exist, instead of being served under the wrong path. Handlers stay plain `def` for the same reason
as in `routers/patients.py`: `Drive.*` blocks on network I/O and on local encryption work, so Starlette's thread pool,
not the event loop, is where it belongs.

Uploads pass through a temporary file instead of holding a whole file in RAM. `Drive.upload` already does this itself
for any source that is not a path or `bytes` (`resources/drives/_source.py`), so an `UploadFile`'s spooled file gets a
second, redundant spool. That is a real cost, paid once per upload, in exchange for never needing to know a file's size
before the multipart body finishes parsing. Downloads never touch disk: `iter_download` decrypts lazily, one chunk at a
time, and `StreamingResponse` forwards each chunk as it is produced, so memory is bounded by one chunk and the first
bytes go out before the last ones arrive from the vault.
"""

from __future__ import annotations

import re
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Path, Query, UploadFile
from fastapi.responses import StreamingResponse

from diagnos import Diagnos, Drive, DriveNode, GroupKeyUnavailable, NotFoundError, Page
from diagnos.api.deps import get_vault
from diagnos.api.document_params import CURSOR_QUERY_HELP, LIMIT_QUERY_HELP
from diagnos.api.errors import ERROR_RESPONSES
from diagnos.api.mtls import ClientIdentity, require_client_certificate
from diagnos.api.schemas import FolderCreated, FolderCreateRequest, NodeView

router = APIRouter(prefix="/v1/drives/{sg}", tags=["drives"], responses=ERROR_RESPONSES)

SecurityGroup = Annotated[str, Path(description="The security group (the drive).")]
NodeId = Annotated[str, Path(description="The file's node id.")]

# CR/LF would let a crafted decrypted filename inject a second header into the response, and quotes or control bytes
# would break the `filename="..."` value. All are replaced rather than rejected, because a node's name is data that a
# caller supplied when uploading, not something this endpoint should refuse to serve over.
_UNSAFE_FILENAME_CHARS = re.compile(r'["\\\x00-\x1f\x7f]')

_FALLBACK_NAME = "file"


def _content_disposition(name: str) -> str:
    """Builds a `Content-Disposition` for a decrypted name: its last path segment, header-safe, non-ASCII kept.

    The web app seals a relative path as the name (`exams/2024/scan.dcm`). A browser saving
    `filename="exams/2024/scan.dcm"` would either reject it or flatten it unpredictably, so only the last segment is
    offered.
    """
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    safe = _UNSAFE_FILENAME_CHARS.sub("_", base).strip()
    if safe in ("", ".", ".."):
        safe = _FALLBACK_NAME
    ascii_fallback = safe.encode("ascii", "replace").decode("ascii")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(safe)}"


def _listed_name(drive: Drive, node: DriveNode) -> str | None:
    """Returns a listed node's name, or `None` when this process holds no key for its group, like document summaries."""
    try:
        return drive.name_of(node)
    except GroupKeyUnavailable:
        return None


def _node_in_group(vault: Diagnos, sg: str, node_id: str) -> DriveNode:
    """Returns the node, or raises the vault's own 404 when it does not exist or belongs to another group."""
    node = vault.drives.get(node_id)
    if node.security_group_id != sg:
        raise NotFoundError(code="DriveNodeNotFound", message=f"no node {node_id!r} in {sg!r}", status=404)
    return node


@router.get(
    "/nodes",
    response_model=Page[NodeView],
    summary="List drive nodes",
    description="One page of files and folders in security group `sg`, each with its name decrypted (`null` when "
    "this process holds no key for the group).",
)
def list_nodes(
    sg: SecurityGroup,
    exam_id: str | None = Query(None, description="Only files linked to this exam."),
    parent_id: str | None = Query(None, description="Folder node id."),
    include_pending: bool = Query(False, description="Include uploads not finished yet."),
    limit: int = Query(50, ge=1, le=200, description=LIMIT_QUERY_HELP),
    cursor: str | None = Query(None, description=CURSOR_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[NodeView]:
    """Lists via `Drive.list`, then decrypts each node's name with `Drive.name_of`."""
    drive = vault.drives.drive(sg)
    page = drive.list(exam_id=exam_id, parent_id=parent_id, include_pending=include_pending, limit=limit, cursor=cursor)
    items = [NodeView(node=node, name=_listed_name(drive, node)) for node in page.items]
    return Page(items=items, next_cursor=page.next_cursor)


@router.get(
    "/nodes/{node_id}",
    response_model=NodeView,
    summary="Get one drive node",
    description="One ready file's metadata plus its decrypted name.",
)
def get_node(
    sg: SecurityGroup,
    node_id: NodeId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> NodeView:
    """Delegates to `Drives.get` and `Drives.name_of`."""
    node = _node_in_group(vault, sg, node_id)
    return NodeView(node=node, name=vault.drives.name_of(node))


@router.post(
    "/nodes",
    response_model=DriveNode,
    status_code=201,
    summary="Upload a file",
    description="Encrypts and uploads `file` into security group `sg`, optionally inside folder `parent_id` "
    "and linked to `exam_id`; single `PUT` or multipart is chosen by the SDK from its size. The whole multipart "
    "body is buffered (`python-multipart`'s `SpooledTemporaryFile`, 1 MiB in RAM before it spills to disk) "
    "before this handler even runs, so request size is what bounds memory, not this endpoint's own logic.",
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
    """Passes the already-spooled `UploadFile.file` straight to `Drive.upload`."""
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
    summary="Create a folder",
    description="Creates a folder in security group `sg` (its name sealed like a file's); pass the returned "
    "`node_id` as `parent_id` when uploading.",
)
def create_folder(
    sg: SecurityGroup,
    body: FolderCreateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> FolderCreated:
    """Delegates to `Drive.create_folder`."""
    node_id = vault.drives.drive(sg).create_folder(body.name, parent_id=body.parent_id)
    return FolderCreated(node_id=node_id)


@router.get(
    "/nodes/{node_id}/content",
    summary="Download decrypted content",
    description="Streams the decrypted bytes of one file, with its decrypted (sanitized) name in "
    "`Content-Disposition`.",
)
def download_node_content(
    sg: SecurityGroup,
    node_id: NodeId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> StreamingResponse:
    """Streams `Drives.iter_download` straight into the response: no temp file, one chunk in RAM."""
    drives = vault.drives
    node = _node_in_group(vault, sg, node_id)
    headers = {"content-disposition": _content_disposition(drives.name_of(node) or node_id)}
    media_type = node.mime_type or "application/octet-stream"
    return StreamingResponse(drives.iter_download(node_id), media_type=media_type, headers=headers)
