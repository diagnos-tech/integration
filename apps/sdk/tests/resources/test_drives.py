"""`Drives`/`Drive` against the `/nodes` double: keys, single and multipart upload, SSE-C, folders, download.

Every assertion about bytes re-derives the keys independently (the node's
wrapped DEK, the content key, the SSE-C sister) and opens what the double
stored — the same way the web app or the vault's processor would.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest

from diagnos.crypto import (
    NODE_DEK_INFO,
    NODE_NAME_INFO,
    SecretBox,
    decrypt_bytes,
    decrypt_content,
    derive_content_key,
    derive_sse_c_key,
    encrypted_size,
    sse_c_headers,
    unwrap_key,
)
from diagnos.errors import ConflictError, CryptoError, NotFoundError, ProtocolError, VaultError
from diagnos.models import DriveNode
from diagnos.resources.drives import Drive, Drives, UploadSource

from vault_double import WORKSPACE_ID, Harness, harness  # noqa: F401 — `harness` is a fixture

_NODES = f"/api/external/v1/workspaces/{WORKSPACE_ID}/nodes"


def _drives(h: Harness) -> Drives:
    """`vault.drives` wired to `h`."""
    return Drives(h.transport, h.keyring_provider, h.entropy, workspace_id=WORKSPACE_ID)


def _drive(h: Harness, group: str = "sg1") -> Drive:
    """One group's drive."""
    return _drives(h).drive(group)


def _dek(h: Harness, node: DriveNode) -> SecretBox:
    """The node's DEK, unwrapped without the SDK's drive code."""
    group_key = h.keyring.group_key(node.security_group_id)
    return unwrap_key(group_key, node.encrypted_keys[node.security_group_id], NODE_DEK_INFO)


def _context(h: Harness, node_id: str) -> str:
    """The `security_context` the double hands out for a node."""
    return h.vault.security_context("nodes", node_id, node_id)["value"]


def _stage_bodies(h: Harness) -> list[dict[str, object]]:
    """Every `POST /nodes/uploads` body, in order."""
    return [
        json.loads(request.content)
        for request in h.vault.api_requests
        if request.method == "POST" and request.url.path == f"{_NODES}/uploads"
    ]


# -- single upload -----------------------------------------------------------


def test_single_upload_seals_a_per_node_key_the_web_app_can_open(harness: Harness) -> None:  # noqa: F811
    """Own DEK wrapped for the group, name under it, body under the content key (node id + context)."""
    plaintext = b"DICM" * 100

    node = _drive(harness).upload(plaintext, name="IM-0001.dcm")

    assert (node.status, node.mode, node.kind) == ("ready", "single", "file")
    assert node.mime_type == "application/dicom"
    assert node.declared_size == node.size == encrypted_size(len(plaintext))
    dek = _dek(harness, node)
    assert decrypt_content(dek, node.encrypted_name, NODE_NAME_INFO) == b"IM-0001.dcm"
    stored = harness.vault._objects[harness.vault.node_url(node.node_id)]  # noqa: SLF001
    assert decrypt_bytes(derive_content_key(dek, node.node_id, _context(harness, node.node_id)), stored) == plaintext


def test_single_put_carries_the_signed_size_and_the_sse_c_sister_key(harness: Harness) -> None:  # noqa: F811
    """`upload.headers` verbatim plus the SSE-C trio derived from the node's own key."""
    node = _drive(harness).upload(b"x" * 10, name="a.txt")

    put = harness.vault.put_requests[-1]
    expected = sse_c_headers(derive_sse_c_key(_dek(harness, node), node.node_id, _context(harness, node.node_id)))
    assert put.headers["content-length"] == str(len(put.content))
    for name, value in expected.items():
        assert put.headers[name] == value


def test_stage_body_is_what_the_vault_validates(harness: Harness) -> None:  # noqa: F811
    """Group in the body, one entry per file with a stable `client_ref`, sealed name and wrapped key."""
    _drive(harness).upload(b"abc", name="note.pdf", exam_id="exam_1")

    (body,) = _stage_bodies(harness)
    (entry,) = body["files"]  # type: ignore[misc]
    assert body["security_group_id"] == "sg1"
    assert body["exam_id"] == "exam_1"
    assert set(entry) == {"client_ref", "encrypted_name", "encrypted_keys", "size", "mime_type"}
    assert set(entry["encrypted_keys"]) == {"sg1"}
    assert entry["mime_type"] == "application/pdf"
    assert len(entry["client_ref"]) <= 64


def test_download_round_trips_with_sse_c_on_the_get(harness: Harness, tmp_path: Path) -> None:  # noqa: F811
    """`download` to bytes, to a path and to a file object; the `GET` presents the same SSE-C key."""
    drive = _drive(harness)
    node = drive.upload(b"exam content", name="report.pdf")
    target = tmp_path / "out.pdf"
    buffer = io.BytesIO()

    assert drive.download(node.node_id) == b"exam content"
    assert drive.download(node.node_id, target) is None
    assert drive.download(node.node_id, buffer) is None
    assert target.read_bytes() == buffer.getvalue() == b"exam content"
    assert harness.vault.get_requests[-1].headers["x-amz-server-side-encryption-customer-algorithm"] == "AES256"
    assert drive.name_of(drive.get(node.node_id)) == "report.pdf"


def test_upload_accepts_paths_and_streams_and_names_them(harness: Harness, tmp_path: Path) -> None:  # noqa: F811
    """A path is named after its file; an open file after its `name`; anonymous bytes need `name=`."""
    path = tmp_path / "scan.png"
    path.write_bytes(b"\x89PNG....")
    drive = _drive(harness)

    with path.open("rb") as handle:
        nodes = drive.upload_many([path, UploadSource(handle), UploadSource(io.BytesIO(b"raw"), name="raw.zzz")])

    assert [drive.name_of(node) for node in nodes] == ["scan.png", "scan.png", "raw.zzz"]
    assert [node.mime_type for node in nodes] == ["image/png", "image/png", None]
    with pytest.raises(ValueError, match="name="):
        drive.upload(b"no name")


def test_upload_many_reserves_one_hundred_at_a_time_and_confirms_together(harness: Harness) -> None:  # noqa: F811
    """150 files → two reservations (100 + 50); results come back in input order."""
    drive = _drive(harness)
    sources = [UploadSource(f"file {i}".encode(), name=f"f{i:03d}.txt") for i in range(150)]

    nodes = drive.upload_many(sources)

    assert [len(body["files"]) for body in _stage_bodies(harness)] == [100, 50]  # type: ignore[arg-type]
    assert [drive.name_of(node) for node in nodes] == [f"f{i:03d}.txt" for i in range(150)]
    assert all(node.status == "ready" for node in nodes)


def test_a_put_that_never_landed_is_reported(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """`missing` on confirmation raises `UploadIncomplete`."""
    real = harness.vault.handle_storage

    def drop(request: httpx.Request) -> httpx.Response:
        """Answers a `PUT` with an `ETag` but never actually stores the bytes."""
        if request.method == "PUT":
            return httpx.Response(200, headers={"ETag": '"x"'})
        return real(request)

    monkeypatch.setattr(harness.vault, "handle_storage", drop)
    harness.transport._storage_client = httpx.Client(transport=httpx.MockTransport(harness.vault.handle_storage))  # noqa: SLF001

    with pytest.raises(ConflictError) as raised:
        _drive(harness).upload(b"lost", name="lost.txt")
    assert raised.value.code == "UploadIncomplete"


def test_a_signed_size_that_does_not_match_is_refused_before_the_put(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reservation signed for another size is a `ProtocolError`, with nothing sent to storage."""
    real = harness.vault._signed_upload  # noqa: SLF001
    monkeypatch.setattr(harness.vault, "_signed_upload", lambda url, size: real(url, size + 1))

    with pytest.raises(ProtocolError):
        _drive(harness).upload(b"abc", name="a.txt")
    assert harness.vault.put_requests == []


# -- multipart -----------------------------------------------------------------


def _small_parts(h: Harness, part_size: int = 64) -> None:
    """Makes every file multipart, with tiny parts."""
    h.vault.single_threshold = 0
    h.vault.part_size = part_size


def test_multipart_streams_parts_with_sse_c_and_the_body_opens(harness: Harness) -> None:  # noqa: F811
    """Parts cut the framed body at arbitrary offsets, each with the SSE-C trio; the result opens."""
    _small_parts(harness)
    plaintext = bytes(range(256)) * 3

    node = _drive(harness).upload(plaintext, name="video.mp4")

    assert (node.mode, node.status) == ("multipart", "ready")
    assert node.size == encrypted_size(len(plaintext))
    part_puts = [r for r in harness.vault.put_requests if "/parts/" in str(r.url)]
    assert len(part_puts) == -(-encrypted_size(len(plaintext)) // 64)
    assert all("x-amz-server-side-encryption-customer-key" in r.headers for r in part_puts)
    assert _drive(harness).download(node.node_id) == plaintext


def test_multipart_signs_parts_in_waves_of_two_hundred(harness: Harness) -> None:  # noqa: F811
    """450 parts → three signing calls (200, 200, 50), made as the upload advances."""
    _small_parts(harness, part_size=16)
    plaintext = b"z" * (450 * 16 - 24 - 21)  # exactly 450 parts once sealed

    _drive(harness).upload(plaintext, name="big.bin")

    assert [len(batch) for batch in harness.vault.signed_part_batches] == [200, 200, 50]
    assert harness.vault.signed_part_batches[1][0] == 201


def test_multipart_opens_the_upload_itself_when_the_batch_did_not(harness: Harness) -> None:  # noqa: F811
    """Without an inline `upload_id`, the SDK calls the recovery route first."""
    _small_parts(harness)
    harness.vault.inline_multipart = False

    node = _drive(harness).upload(b"q" * 300, name="q.bin")

    assert f"POST {_NODES}/{node.node_id}/multipart" in [f"{r.method} {r.url.path}" for r in harness.vault.api_requests]
    assert node.status == "ready"


def test_a_failed_multipart_is_aborted(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """A part that fails aborts the upload, so the vault releases the reserved bytes, then re-raises."""
    _small_parts(harness)
    real = harness.vault.handle_storage

    def fail_second_part(request: httpx.Request) -> httpx.Response:
        """Fails only the second part's `PUT`, so the upload must abort mid-flight."""
        return httpx.Response(500) if str(request.url).endswith("/2") else real(request)

    harness.transport._storage_client = httpx.Client(transport=httpx.MockTransport(fail_second_part))  # noqa: SLF001

    with pytest.raises(VaultError):
        _drive(harness).upload(b"w" * 300, name="w.bin")
    assert len(harness.vault.aborted) == 1


def test_a_part_without_an_etag_is_a_protocol_error(harness: Harness) -> None:  # noqa: F811
    """Storage must return an `ETag` per part."""
    _small_parts(harness)
    harness.transport._storage_client = httpx.Client(  # noqa: SLF001
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )

    with pytest.raises(ProtocolError):
        _drive(harness).upload(b"e" * 300, name="e.bin")


# -- folders, listing, reading -----------------------------------------------


def test_folders_hold_files_and_filter_the_listing(harness: Harness) -> None:  # noqa: F811
    """A folder is a ready node with a sealed name; `parent_id` places files in it and filters the list."""
    drive = _drive(harness)
    folder_id = drive.create_folder("Résumé 1")
    inner = drive.upload(b"1", name="IM-1.dcm", parent_id=folder_id)
    drive.upload(b"2", name="outside.txt")

    in_folder = drive.list(parent_id=folder_id)
    folder = next(node for node in drive.iter_all() if node.node_id == folder_id)

    assert [node.node_id for node in in_folder] == [inner.node_id]
    assert (folder.kind, folder.status) == ("folder", "ready")
    assert drive.name_of(folder) == "Résumé 1"
    with pytest.raises(NotFoundError):
        drive.get(folder_id)
    assert _drive(harness).create_folder("sub", parent_id=folder_id)


def test_workspace_listing_crosses_groups_and_filters(harness: Harness) -> None:  # noqa: F811
    """`vault.drives.list` sees every group; `security_group`/`exam_id`/`include_pending` narrow it."""
    drives = _drives(harness)
    a = drives.drive("sg1").upload(b"a", name="a.txt", exam_id="exam_1")
    b = drives.drive("sg2").upload(b"b", name="b.txt")

    everything = [node.node_id for node in drives.iter_all(limit=1)]
    only_sg2 = [node.node_id for node in drives.list(security_group="sg2")]
    of_exam = [node.node_id for node in drives.drive("sg1").iter_all(exam_id="exam_1")]

    assert everything == sorted([a.node_id, b.node_id])
    assert only_sg2 == [b.node_id]
    assert of_exam == [a.node_id]
    assert drives.get(a.node_id).node_id == a.node_id
    assert drives.name_of(b) == "b.txt"
    assert drives.download(b.node_id) == b"b"
    assert b"".join(drives.iter_download(a.node_id)) == b"a"
    query = harness.vault.api_requests[-1].url.params
    assert "include_pending" not in query
    drives.list(include_pending=True)
    assert harness.vault.api_requests[-1].url.params["include_pending"] == "true"


def test_a_node_without_its_group_key_fails_closed(harness: Harness) -> None:  # noqa: F811
    """No group key, no DEK; a node whose map lacks its own group is a `CryptoError`."""
    drive = _drive(harness)
    node = drive.upload(b"secret", name="s.txt")
    orphan = node.model_copy(update={"encrypted_keys": {}})

    with pytest.raises(CryptoError):
        drive.name_of(orphan)
    del harness.keyring.group_keys["sg1"]
    with pytest.raises(Exception, match="sg1"):
        drive.download(node.node_id)
    assert drive.security_group_id == "sg1"
