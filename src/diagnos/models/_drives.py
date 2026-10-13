"""🇺🇸 The drive domain (`docs/PROTOCOL.md §9`): one workspace's files and folders, and the upload-staging plan.

🇧🇷 O domínio de drive (`docs/PROTOCOL.md §9`): arquivos e pastas de um workspace, e o plano de reserva de upload.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from diagnos.crypto import EncryptedPayload

DriveNodeStatus = Literal["pending", "ready", "failed"]
DriveNodeKind = Literal["file", "folder"]
DriveUploadMode = Literal["single", "multipart"]
DriveMediaKind = Literal["image", "video", "dicom", "other"]


class OptimizedVariant(BaseModel):
    """🇺🇸 A derived rendition the vault's processor made from a node (thumbnail, WebP, DICOM instance, stream).

    🇧🇷 Uma derivação que o processador do cofre fez a partir de um nó (miniatura, WebP, instância DICOM, stream).
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    storage_bucket: str
    storage_path: str
    storage_size: int
    storage_mime_type: str
    created_at: str


class DriveNode(BaseModel):
    """🇺🇸 One file or folder of a workspace (`docs/PROTOCOL.md §9`) — the vault's index of it, never its content.

    Every node has its own DEK, wrapped for its security group in
    `encrypted_keys`; the name stays sealed in `encrypted_name` until
    `name_of` opens it on demand (doing it eagerly for a whole page would
    mean an AES-GCM per row nobody asked for). A folder has no content and
    no upload fields; a file's `size` is what the vault measured, never just
    what was declared.

    🇧🇷 Um arquivo ou pasta de um workspace (`docs/PROTOCOL.md §9`) — o índice que o cofre tem dele, nunca o conteúdo.

    Todo nó tem a própria DEK, embrulhada para o security group em
    `encrypted_keys`; o nome fica selado em `encrypted_name` até `name_of`
    abri-lo sob demanda (fazer isso para uma página inteira significaria um
    AES-GCM por linha que ninguém pediu). Uma pasta não tem conteúdo nem
    campos de upload; o `size` de um arquivo é o que o cofre mediu, nunca só
    o declarado.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    workspace_id: str
    security_group_id: str
    kind: DriveNodeKind = "file"
    status: DriveNodeStatus
    exam_id: str | None = None
    parent_id: str | None = None
    mode: DriveUploadMode | None = None
    media_kind: DriveMediaKind | None = None
    declared_size: int | None = None
    size: int | None = None
    mime_type: str | None = None
    encrypted_name: EncryptedPayload
    encrypted_keys: dict[str, EncryptedPayload]
    storage_path: str | None = None
    optimized_variants: list[OptimizedVariant] = Field(default_factory=list)
    processing_status: str | None = None
    processing_error: str | None = None
    total_size: int | None = None
    created_by: str
    created_at: str
    completed_at: str | None = None
    is_deleted: bool = False


class SecurityContext(BaseModel):
    """🇺🇸 The opaque value the vault binds an object's keys to, returned next to every signed URL (§7).

    🇧🇷 O valor opaco ao qual o cofre amarra as chaves de um objeto, devolvido junto de toda URL assinada (§7).
    """

    model_config = ConfigDict(frozen=True)

    value: str
    kid: str | None = None


class StagedNode(BaseModel):
    """🇺🇸 One entry of the `POST /nodes/uploads` answer (`docs/PROTOCOL.md §9`) — a plan, not a finished node.

    Internal to `resources/drives`: it says, per file, whether to take the
    single-`PUT` path (`upload` is set) or the multipart one (`part_size`,
    and usually an already-open `upload_id`), and carries the
    `security_context` the file's content key is derived from.

    🇧🇷 Uma entrada da resposta de `POST /nodes/uploads` (`docs/PROTOCOL.md §9`) — um plano, não um nó pronto.

    Interno a `resources/drives`: diz, por arquivo, se segue o caminho de
    `PUT` único (`upload` presente) ou o multipart (`part_size`, e em geral um
    `upload_id` já aberto), e carrega o `security_context` de que a chave de
    conteúdo do arquivo é derivada.
    """

    model_config = ConfigDict(frozen=True)

    client_ref: str
    node_id: str
    version_id: str
    security_context: SecurityContext
    kind: DriveNodeKind = "file"
    mode: DriveUploadMode | None = None
    upload: dict[str, Any] | None = None
    part_size: int | None = None
    part_count: int | None = None
    upload_id: str | None = None
