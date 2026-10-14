"""The sandbox every runnable doc snippet runs in: the real SDK, an in-memory vault, nothing else faked.

`from diagnos import Diagnos; Diagnos()` inside a snippet is the real class
doing the real work — token parsing, enrollment with a real hybrid key
pair, request signing, sealing and opening every record and file in the
Rust enclave. Only the network is replaced: the two `httpx` clients
`VaultTransport` would open are swapped for `httpx.MockTransport`s that
answer from `FakeVault`, the SDK's own test double of the vault and R2
(`apps/sdk/tests/resources/vault_double/`), plus the two enrollment
routes, where every registration is approved on the first poll with the
groups `sg_oncology` and `sg_radiology`.

The working directory is a fresh temporary folder holding the files the
guides upload (`FIXTURES`), and the environment carries a sandbox
`DIAGNOS_API_TOKEN` — so a snippet reads exactly like production code.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import secrets
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import httpx

import diagnos.client
from diagnos.crypto.hybrid import seal_hybrid
from diagnos.transport.http import VaultTransport

from .output import REPO_ROOT

# The SDK's vault double lives with its tests, outside any package; this is the one place that reaches it.
sys.path.insert(0, str(REPO_ROOT / "apps" / "sdk" / "tests" / "resources"))
from vault_double import VAULT_URL, WORKSPACE_ID, FakeVault  # noqa: E402

GRANTED_GROUPS = ("sg_oncology", "sg_radiology")
FIXTURES: dict[str, bytes] = {
    "scans/IM-0001.dcm": b"DICM" + bytes(128),
    "scans/IM-0002.dcm": b"DICM" + bytes(256),
    "photo.jpg": b"\xff\xd8\xff\xe0" + bytes(64),
    "report.pdf": b"%PDF-1.7\n" + bytes(64),
}
_REGISTRY = f"/api/external/v1/workspaces/{WORKSPACE_ID}/session/registry"
_LOCK = "/api/external/v1/session/lock"
_SESSION_SECONDS = 3600


def _b64url(data: bytes) -> str:
    """Returns unpadded base64url (`docs/PROTOCOL.md §0`)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    """Returns the bytes of an unpadded base64url string, the inverse of `_b64url`."""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sandbox_token() -> str:
    """Returns an `apikey-<jwt>` for the double's workspace; the SDK never verifies the signature, so none is real."""
    header = _b64url(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode())
    claims = {"sub": "key_docs", "account_id": "acc_docs", "workspace_id": WORKSPACE_ID, "name": "docs@ws_1"}
    return f"apikey-{header}.{_b64url(json.dumps(claims).encode())}.{_b64url(b'sandbox')}"


def _envelope(result: object, status: int = 200) -> httpx.Response:
    """Returns a `success: true` envelope (`docs/PROTOCOL.md §0`)."""
    body = {"success": True, "status": "success", "status_code": status, "result": result, "docs": "sandbox"}
    return httpx.Response(status, json=body)


class SandboxVault:
    """`FakeVault` plus enrollment: registrations approved at the first poll, sealed to the SDK's own keys."""

    def __init__(self) -> None:
        """Creates an empty workspace with two granted groups."""
        self.documents = FakeVault()
        self.group_deks = {group: secrets.token_bytes(32) for group in GRANTED_GROUPS}
        self._public_keys: dict[str, tuple[bytes, bytes]] = {}

    def handle_api(self, request: httpx.Request) -> httpx.Response:
        """Answers the enrollment and lock routes itself and hands every other request to `FakeVault`."""
        path = request.url.path
        if request.method == "POST" and path == _REGISTRY:
            return self._register(json.loads(request.content))
        if request.method == "GET" and path.startswith(f"{_REGISTRY}/"):
            return self._approve(path.rsplit("/", 1)[1])
        if request.method == "POST" and path == _LOCK:
            return _envelope({"locked": True})
        return self.documents.handle_api(request)

    def _register(self, body: dict[str, Any]) -> httpx.Response:
        """Answers `POST session/registry`: remembers the public keys, hands out a link and a code."""
        enrollment_id = f"enr_{len(self._public_keys) + 1}"
        keys = body["public_keys"]
        self._public_keys[enrollment_id] = (_b64url_decode(keys["x25519"]), _b64url_decode(keys["mlkem768"]))
        registration = {
            "enrollment_id": enrollment_id,
            "code": "482915",
            "approval_url": f"https://app.diagnos.health/approve/{enrollment_id}",
            "expires_at": int(time.time()) + 600,
            "poll_interval_seconds": 0,
        }
        return _envelope(registration, status=201)

    def _approve(self, enrollment_id: str) -> httpx.Response:
        """Answers `GET session/registry/{id}`: approved, with the session and group keys sealed to that enrollment."""
        x25519, mlkem768 = self._public_keys[enrollment_id]
        expires_at = int(time.time()) + _SESSION_SECONDS
        session = {
            "session_id": f"ses_{enrollment_id}",
            "sign_key": _b64url(secrets.token_bytes(32)),
            "enc_key": _b64url(secrets.token_bytes(32)),
            "expires_at": expires_at,
        }
        sealed_session = seal_hybrid(x25519, mlkem768, json.dumps(session).encode(), enrollment_id)
        sealed_groups = {
            group: seal_hybrid(x25519, mlkem768, dek, enrollment_id).to_dict() for group, dek in self.group_deks.items()
        }
        approval = {
            "session_id": session["session_id"],
            "session_expires_at": expires_at,
            "sealed_session": sealed_session.to_dict(),
            "sealed_group_keys": sealed_groups,
        }
        return _envelope({"status": "approved", "approval": approval})


def _transport_factory(vault: SandboxVault) -> Any:
    """Returns a stand-in for `VaultTransport` inside `diagnos.client`: the real class, with mock clients injected."""

    def build(*args: Any, **kwargs: Any) -> VaultTransport:
        """Builds the transport from what `Diagnos` passes, plus the two mock clients."""
        api = httpx.Client(transport=httpx.MockTransport(vault.handle_api), base_url=VAULT_URL)
        storage = httpx.Client(transport=httpx.MockTransport(vault.documents.handle_storage))
        return VaultTransport(*args, client=api, storage_client=storage, **kwargs)

    return build


@contextlib.contextmanager
def sandbox() -> Iterator[SandboxVault]:
    """Provides everything a snippet needs and undoes it on exit: environment, working directory, patched transport.

    `DIAGNOS_HARDEN_PROCESS=0` keeps the checking process debuggable: the
    hardening itself is the enclave's business, not the docs'.

    Yields:
        The `SandboxVault` behind the patched transport.
    """
    vault = SandboxVault()
    with (
        tempfile.TemporaryDirectory(prefix="diagnos-docs-") as workdir,
        mock.patch.dict(os.environ),
        mock.patch.object(diagnos.client, "VaultTransport", _transport_factory(vault)),
    ):
        for key in [key for key in os.environ if key.startswith(("DIAGNOS_", "OPENBAO_"))]:
            del os.environ[key]
        os.environ.update(
            {"DIAGNOS_API_TOKEN": sandbox_token(), "DIAGNOS_VAULT_URL": VAULT_URL, "DIAGNOS_HARDEN_PROCESS": "0"}
        )
        for name, content in FIXTURES.items():
            (Path(workdir) / name).parent.mkdir(parents=True, exist_ok=True)
            (Path(workdir) / name).write_bytes(content)
        with contextlib.chdir(workdir):
            yield vault
