"""`_Nodes`: what happens when the vault's reservation answer breaks the protocol it is supposed to speak.

`test_drives.py` proves the happy paths and the failures a real
`FakeVault` can produce on its own (a missing `ETag`, a `PUT` that never
landed). The scenarios here — a reservation missing a file node entirely,
one claiming an unknown upload mode, a single-mode node with no upload URL
— are protocol violations `FakeVault` itself never generates, so `_stage`
is monkeypatched directly (on the instance, per-test) to hand back exactly
the malformed answer each defensive check exists for. The last test proves
the one property `test_a_failed_multipart_is_aborted` cannot: that an
abort which itself fails never replaces the original error.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from diagnos.errors import ProtocolError, VaultError
from diagnos.models import SecurityContext, StagedNode
from diagnos.resources.drives import Drive, Drives

from vault_double import WORKSPACE_ID, Harness, harness  # noqa: F401 — `harness` is a fixture


def _drive(h: Harness, group: str = "sg1") -> Drive:
    """One group's drive; `._nodes` is its `_Nodes` engine."""
    drives = Drives(h.transport, h.keyring_provider, h.entropy, workspace_id=WORKSPACE_ID)
    return drives.drive(group)


def _staged_stub(client_ref: str, **overrides: Any) -> StagedNode:
    """A minimal, otherwise-valid `StagedNode` a real reservation would never actually send."""
    fields: dict[str, Any] = {
        "client_ref": client_ref,
        "node_id": "node_x",
        "version_id": "node_x",
        "security_context": SecurityContext(value="ctx", kid=None),
        "kind": "file",
    }
    fields.update(overrides)
    return StagedNode(**fields)


def test_a_reservation_answering_no_file_node_is_a_protocol_error(harness: Harness) -> None:  # noqa: F811
    """A reservation that answers with a folder (or nothing) for a file `client_ref` is `ProtocolError`."""
    drive = _drive(harness)

    def fake_stage(body: dict[str, Any]) -> list[StagedNode]:
        """Answers a file upload's reservation with a folder node, which never happens for real."""
        (entry,) = body["files"]
        return [_staged_stub(entry["client_ref"], kind="folder")]

    drive._nodes._stage = fake_stage  # type: ignore[method-assign]  # noqa: SLF001 — simulating a protocol violation

    with pytest.raises(ProtocolError, match="did not return a file node"):
        drive.upload(b"content", name="a.txt")


def test_a_reservation_claiming_an_unknown_upload_mode_is_a_protocol_error(harness: Harness) -> None:  # noqa: F811
    """A staged file node with no recognized `mode` (`None`, the shape a folder carries) is `ProtocolError`.

    `StagedNode.mode` is a closed `Literal["single", "multipart"] | None` —
    real reservations can never send a made-up third string — so the one
    way to reach `_upload_batch`'s `else` branch is a `kind="file"` entry
    that nonetheless carries `mode=None`, the value only a folder is
    supposed to have.
    """
    drive = _drive(harness)

    def fake_stage(body: dict[str, Any]) -> list[StagedNode]:
        """Answers with a file node whose `mode` is `None` — a shape a real reservation never sends."""
        (entry,) = body["files"]
        return [_staged_stub(entry["client_ref"], mode=None)]

    drive._nodes._stage = fake_stage  # type: ignore[method-assign]  # noqa: SLF001

    with pytest.raises(ProtocolError, match="unknown upload mode None"):
        drive.upload(b"content", name="a.txt")


def test_a_single_mode_node_with_no_upload_url_is_a_protocol_error(harness: Harness) -> None:  # noqa: F811
    """`mode="single"` with no `upload` URL at all is `ProtocolError`, never an `AttributeError` on `None`."""
    drive = _drive(harness)

    def fake_stage(body: dict[str, Any]) -> list[StagedNode]:
        """Answers `mode="single"` with no `upload` at all — a shape a real reservation never sends."""
        (entry,) = body["files"]
        return [_staged_stub(entry["client_ref"], mode="single", upload=None)]

    drive._nodes._stage = fake_stage  # type: ignore[method-assign]  # noqa: SLF001

    with pytest.raises(ProtocolError, match="came without an upload URL"):
        drive.upload(b"content", name="a.txt")


def test_a_failing_abort_never_hides_the_original_multipart_failure(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both a part upload *and* the best-effort abort that follows it fail, the original error wins.

    `_abort`'s own docstring promises it is best-effort — "the vault's sweep
    covers a lost abort" — so a broken abort must never mask what actually
    went wrong first.
    """
    harness.vault.single_threshold = 0
    harness.vault.part_size = 64
    real = harness.vault.handle_storage

    def fail_second_part(request: httpx.Request) -> httpx.Response:
        """Fails only the second part's `PUT`, so the multipart upload must abort mid-flight."""
        return httpx.Response(500) if str(request.url).endswith("/2") else real(request)

    harness.transport._storage_client = httpx.Client(  # noqa: SLF001
        transport=httpx.MockTransport(fail_second_part)
    )

    real_post = harness.transport.post

    def post_and_break_abort(
        path: str, *, json: Any | None = None, query: Any | None = None, signed: bool = True
    ) -> Any:
        """Passes every `POST` through except the abort route, which raises instead."""
        if path.endswith("/multipart/abort"):
            raise RuntimeError("the abort route is down too")
        return real_post(path, json=json, query=query, signed=signed)

    monkeypatch.setattr(harness.transport, "post", post_and_break_abort)

    with pytest.raises(VaultError):  # the ORIGINAL 500, never the abort's RuntimeError
        _drive(harness).upload(b"w" * 300, name="w.bin")
