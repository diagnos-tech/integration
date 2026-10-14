"""The drive domain (`docs/PROTOCOL.md §9`): one workspace's files and folders, and the upload-staging plan."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from diagnos.crypto import EncryptedPayload

DriveNodeStatus = Literal["pending", "ready", "failed"]
DriveNodeKind = Literal["file", "folder"]
DriveUploadMode = Literal["single", "multipart"]
DriveMediaKind = Literal["image", "video", "dicom", "other"]


class OptimizedVariant(BaseModel):
    """A derived rendition the vault's processor made from a node, such as a thumbnail, WebP, DICOM instance or stream.

    Attributes:
        kind: The kind of rendition.
        storage_bucket: The bucket that holds the rendition.
        storage_path: The object path inside the bucket.
        storage_size: The size of the stored object, in bytes.
        storage_mime_type: The MIME type of the stored object.
        created_at: When the rendition was created, as an ISO 8601 instant.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    storage_bucket: str
    storage_path: str
    storage_size: int
    storage_mime_type: str
    created_at: str


class DriveNode(BaseModel):
    """One file or folder of a workspace (`docs/PROTOCOL.md §9`): the vault's index of it, never its content.

    Every node has its own DEK, wrapped for its security group in
    `encrypted_keys`. The name stays sealed in `encrypted_name` until
    `name_of` opens it on demand (doing it eagerly for a whole page would
    mean an AES-GCM per row nobody asked for). A folder has no content and
    no upload fields. A file's `size` is what the vault measured, never just
    what was declared.

    Attributes:
        node_id: The id of the node.
        workspace_id: The workspace that owns the node.
        security_group_id: The security group whose key protects the node.
        kind: Whether the node is a `file` or a `folder`.
        status: The upload state: `pending`, `ready` or `failed`.
        exam_id: The exam the node was uploaded for, if any.
        parent_id: The id of the containing folder, or `None` at the root.
        mode: How the file was uploaded: `single` or `multipart`.
        media_kind: The detected media kind: `image`, `video`, `dicom` or `other`.
        declared_size: The size the uploader declared, in bytes.
        size: The size the vault measured, in bytes.
        mime_type: The MIME type of the file.
        encrypted_name: The node's name, sealed under the node's DEK.
        encrypted_keys: The node's DEK, wrapped for each security group that may open it.
        storage_path: The object path in storage.
        optimized_variants: Renditions the vault's processor derived from the file.
        processing_status: The state of the vault's processing, if any.
        processing_error: The processing error message, if processing failed.
        total_size: The total size the vault reports for the node, in bytes.
        created_by: The account that created the node.
        created_at: When the node was created, as an ISO 8601 instant.
        completed_at: When the upload completed, as an ISO 8601 instant.
        is_deleted: Whether the node is deleted.
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
    """The opaque value the vault binds an object's keys to, returned next to every signed URL (§7).

    Attributes:
        value: The opaque security context string.
        kid: The key identifier the vault attached to the context, if any.
    """

    model_config = ConfigDict(frozen=True)

    value: str
    kid: str | None = None


class StagedNode(BaseModel):
    """One entry of the `POST /nodes/uploads` answer (`docs/PROTOCOL.md §9`): a plan, not a finished node.

    Internal to `resources/drives`. It says, per file, whether to take the
    single-`PUT` path (`upload` is set) or the multipart one (`part_size`,
    and usually an already-open `upload_id`), and it carries the
    `security_context` the file's content key is derived from.
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
