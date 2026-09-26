"""🇺🇸 The drives half of the double: nodes (files and folders), single and multipart upload.

`§13`'s `content_length` limit does not apply to this double — a huge `_DEFAULT_SINGLE_THRESHOLD` just
means "everything is 'single' unless a test lowers it", mirroring `services/uploads`' own
single-vs-multipart cutoff.

🇧🇷 A metade de drives do duplo: nós (arquivos e pastas), upload único e multipart.

O limite de `content_length` de `§13` não vale para este duplo — um `_DEFAULT_SINGLE_THRESHOLD` enorme
só significa "tudo é 'single' a menos que um teste o abaixe", espelhando o corte single-vs-multipart de
`services/uploads`.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import httpx

from ._wire import ACTOR, WORKSPACE_ID, _envelope_success, _VaultRefusal

if TYPE_CHECKING:
    from ._core import FakeVault, _RouteHandler

_DEFAULT_SINGLE_THRESHOLD = 1_000_000


class _NodesMixin:
    """🇺🇸 `FakeVault`'s drive half: node reservation, single and multipart upload, listing.

    🇧🇷 A metade de drive do `FakeVault`: reserva de nó, upload único e multipart, listagem.
    """

    def _node_view(self, node_id: str) -> dict[str, Any]:
        """🇺🇸 `NodeResponse`: the stored node, as JSON. 🇧🇷 `NodeResponse`: o nó guardado, como JSON."""
        return json.loads(json.dumps(self._nodes[node_id]))

    def _node(self, node_id: str) -> dict[str, Any]:
        """🇺🇸 The stored node, or `DriveNodeNotFound`. 🇧🇷 O nó guardado, ou `DriveNodeNotFound`."""
        node = self._nodes.get(node_id)
        if node is None:
            raise _VaultRefusal("DriveNodeNotFound", node_id)
        return node

    def node_url(self, node_id: str) -> str:
        """🇺🇸 Where a node's object lives. 🇧🇷 Onde mora o objeto de um nó."""
        return self._object_url(f"workspaces/{WORKSPACE_ID}/nodes/{node_id}")

    def stage_nodes(self, body: dict[str, Any]) -> dict[str, Any]:
        """🇺🇸 `POST /nodes/uploads` — validates like `StageUploadsRequest`, idempotent per `client_ref`.

        🇧🇷 `POST /nodes/uploads` — valida como `StageUploadsRequest`, idempotente por `client_ref`.
        """
        group = body.get("security_group_id")
        files = body.get("files") or []
        if not isinstance(group, str) or not group or not 1 <= len(files) <= 100:
            raise _VaultRefusal("ValidationError", "security_group_id and 1..100 files are required", status=400)
        parent_id = body.get("parent_id")
        if parent_id is not None:
            parent = self._nodes.get(parent_id)
            if parent is None or parent["kind"] != "folder" or parent["security_group_id"] != group:
                raise _VaultRefusal("DriveInvalidParent", str(parent_id), status=400)
        self.stage_calls += 1
        items = []
        for entry in files:
            kind = entry.get("kind", "file")
            keys = {"kind", "client_ref", "encrypted_name", "encrypted_keys"} | (
                {"size", "mime_type"} if kind == "file" else set()
            )
            if set(entry) - keys or group not in entry.get("encrypted_keys", {}) or "encrypted_name" not in entry:
                raise _VaultRefusal("ValidationError", f"bad entry {sorted(entry)}", status=400)
            ref = entry["client_ref"]
            node_id = self._refs.get(ref)
            if node_id is None:
                node_id = self._refs[ref] = self._next_id("node")
                self._nodes[node_id] = self._new_node(node_id, group, entry, body, kind)
            items.append(self._staged_item(ref, node_id))
        return {"items": items}

    def _new_node(
        self, node_id: str, group: str, entry: dict[str, Any], body: dict[str, Any], kind: str
    ) -> dict[str, Any]:
        """🇺🇸 A freshly reserved node (a folder is ready at once). 🇧🇷 Um nó recém-reservado (pasta já pronta)."""
        node: dict[str, Any] = {
            "node_id": node_id,
            "workspace_id": WORKSPACE_ID,
            "security_group_id": group,
            "kind": kind,
            "status": "ready" if kind == "folder" else "pending",
            "encrypted_name": entry["encrypted_name"],
            "encrypted_keys": entry["encrypted_keys"],
            "optimized_variants": [],
            "created_by": ACTOR,
            "created_at": self.now(),
            "is_deleted": False,
        }
        for field_name in ("exam_id", "parent_id"):
            if body.get(field_name) is not None:
                node[field_name] = body[field_name]
        if kind == "file":
            size = entry["size"]
            node.update(
                mode="single" if size <= self.single_threshold else "multipart",
                declared_size=size,
                media_kind="dicom" if entry.get("mime_type") == "application/dicom" else "other",
                storage_path=f"workspaces/{WORKSPACE_ID}/nodes/{node_id}",
            )
            if "mime_type" in entry:
                node["mime_type"] = entry["mime_type"]
            if node["mode"] == "multipart":
                self._multipart[node_id] = {"upload_id": self._next_id("mpu") if self.inline_multipart else None}
        return node

    def _staged_item(self, ref: str, node_id: str) -> dict[str, Any]:
        """🇺🇸 One `StagedNodeResponse`. 🇧🇷 Um `StagedNodeResponse`."""
        node = self._nodes[node_id]
        item: dict[str, Any] = {
            "client_ref": ref,
            "node_id": node_id,
            "version_id": node_id,
            "security_context": self.security_context("nodes", node_id, node_id),
            "kind": node["kind"],
        }
        if node["kind"] == "folder":
            return item
        item["mode"] = node["mode"]
        if node["mode"] == "single":
            item["upload"] = self._signed_upload(self.node_url(node_id), node["declared_size"])
        else:
            item["part_size"] = self.part_size
            item["part_count"] = -(-node["declared_size"] // self.part_size)
            upload_id = self._multipart[node_id]["upload_id"]
            if upload_id is not None:
                item["upload_id"] = upload_id
        return item

    def complete_single(self, node_ids: list[str]) -> dict[str, Any]:
        """🇺🇸 `POST /nodes/uploads/complete` — `ready` for every object that landed, `missing` for the rest.

        🇧🇷 `POST /nodes/uploads/complete` — `ready` para todo objeto que chegou, `missing` para o resto.
        """
        ready, missing = [], []
        for node_id in node_ids:
            node = self._node(node_id)
            stored = self._objects.get(self.node_url(node_id))
            if stored is None:
                missing.append(node_id)
                continue
            node.update(status="ready", size=len(stored), total_size=len(stored), completed_at=self.now())
            ready.append(self._node_view(node_id))
        return {"ready": ready, "missing": missing}

    def start_multipart(self, node_id: str) -> dict[str, Any]:
        """🇺🇸 `POST /nodes/{id}/multipart` — the recovery route when the batch did not open the upload.

        🇧🇷 `POST /nodes/{id}/multipart` — a rota de recuperação quando o lote não abriu o upload.
        """
        node = self._node(node_id)
        state = self._multipart[node_id]
        state["upload_id"] = state["upload_id"] or self._next_id("mpu")
        return {
            "upload_id": state["upload_id"],
            "part_size": self.part_size,
            "part_count": -(-node["declared_size"] // self.part_size),
        }

    def sign_parts(self, node_id: str, part_numbers: list[int]) -> dict[str, Any]:
        """🇺🇸 `POST /nodes/{id}/multipart/parts` — at most 200 URLs per call.

        🇧🇷 `POST /nodes/{id}/multipart/parts` — no máximo 200 URLs por chamada.
        """
        self._node(node_id)
        if not 1 <= len(part_numbers) <= 200 or self._multipart[node_id]["upload_id"] is None:
            raise _VaultRefusal("ValidationError", "1..200 part numbers on an open upload", status=400)
        self.signed_part_batches.append(list(part_numbers))
        parts = [
            {"part_number": n, "url": self._part_url(node_id, n), "expires_at": 9_999_999_999} for n in part_numbers
        ]
        return {"parts": parts}

    @staticmethod
    def _part_url(node_id: str, number: int) -> str:
        """🇺🇸 A part's presigned URL. 🇧🇷 A URL pré-assinada de uma parte."""
        return f"https://storage.diagnosusercontent.com/parts/{node_id}/{number}"

    def complete_multipart(self, node_id: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        """🇺🇸 `POST /nodes/{id}/multipart/complete` — assembles the parts in order; the node becomes ready.

        🇧🇷 `POST /nodes/{id}/multipart/complete` — monta as partes em ordem; o nó fica pronto.
        """
        node = self._node(node_id)
        ordered = sorted(parts, key=lambda part: part["part_number"])
        urls = [self._part_url(node_id, part["part_number"]) for part in ordered]
        keys = {self._sse_keys.get(url) for url in urls}
        if len(keys) != 1:
            raise _VaultRefusal("ValidationError", "every part must carry the same SSE-C key", status=400)
        assembled = b"".join(self._objects[url] for url in urls)
        self._objects[self.node_url(node_id)] = assembled
        self._sse_keys[self.node_url(node_id)] = keys.pop()
        node.update(status="ready", size=len(assembled), total_size=len(assembled), completed_at=self.now())
        return {"node": self._node_view(node_id)}

    def abort_multipart(self, node_id: str) -> dict[str, Any]:
        """🇺🇸 `POST /nodes/{id}/multipart/abort` — the node becomes `failed`. 🇧🇷 O nó vira `failed`."""
        self._node(node_id)["status"] = "failed"
        self.aborted.append(node_id)
        return {"aborted": True}

    def list_nodes(self, query: dict[str, str]) -> dict[str, Any]:
        """🇺🇸 `GET /nodes` — ready nodes (unless `include_pending`), filtered and paginated.

        🇧🇷 `GET /nodes` — nós prontos (salvo `include_pending`), filtrados e paginados.
        """
        include_pending = query.get("include_pending") == "true"
        ids = sorted(
            node_id
            for node_id, node in self._nodes.items()
            if include_pending or node["status"] == "ready"
            if all(query.get(name) in (None, node.get(name)) for name in ("security_group_id", "exam_id", "parent_id"))
        )
        limit = int(query.get("limit", 50))
        cursor = query.get("cursor")
        start = ids.index(cursor) + 1 if cursor else 0
        page = ids[start : start + limit]
        next_cursor = page[-1] if start + limit < len(ids) else None
        return {"items": [self._node_view(node_id) for node_id in page], "next_cursor": next_cursor}

    def get_node(self, node_id: str) -> dict[str, Any]:
        """🇺🇸 `GET /nodes/{id}` — a ready file only (pending and folders are `404`), with its download.

        🇧🇷 `GET /nodes/{id}` — só arquivo pronto (pendente e pasta são `404`), com o download.
        """
        node = self._node(node_id)
        if node["status"] != "ready" or node["kind"] != "file":
            raise _VaultRefusal("DriveNodeNotFound", node_id)
        return {
            "node": self._node_view(node_id),
            "security_context": self.security_context("nodes", node_id, node_id),
            "download": self._signed_download(self.node_url(node_id)),
        }


def _stage_nodes_route(
    vault: FakeVault, _groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST /nodes/uploads`. 🇧🇷 `POST /nodes/uploads`."""
    return _envelope_success(vault.stage_nodes(body), status=201)


def _complete_single_route(
    vault: FakeVault, _groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST /nodes/uploads/complete`. 🇧🇷 `POST /nodes/uploads/complete`."""
    return _envelope_success(vault.complete_single(body["node_ids"]))


def _start_multipart_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST /nodes/{id}/multipart`. 🇧🇷 `POST /nodes/{id}/multipart`."""
    return _envelope_success(vault.start_multipart(groups["node_id"]))


def _sign_parts_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST /nodes/{id}/multipart/parts`. 🇧🇷 `POST /nodes/{id}/multipart/parts`."""
    return _envelope_success(vault.sign_parts(groups["node_id"], body["part_numbers"]))


def _complete_multipart_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST /nodes/{id}/multipart/complete`. 🇧🇷 `POST /nodes/{id}/multipart/complete`."""
    return _envelope_success(vault.complete_multipart(groups["node_id"], body["parts"]))


def _abort_multipart_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST /nodes/{id}/multipart/abort`. 🇧🇷 `POST /nodes/{id}/multipart/abort`."""
    return _envelope_success(vault.abort_multipart(groups["node_id"]))


def _list_nodes_route(
    vault: FakeVault, _groups: dict[str, str], query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET /nodes`. 🇧🇷 `GET /nodes`."""
    return _envelope_success(vault.list_nodes(query))


def _get_node_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET /nodes/{id}`. 🇧🇷 `GET /nodes/{id}`."""
    return _envelope_success(vault.get_node(groups["node_id"]))


_NODES = rf"^/api/external/v1/workspaces/{WORKSPACE_ID}/nodes"
# 🇺🇸 Ordered most-specific-first: a literal segment (`complete`, `versions`)
# must be tried before the catch-all `{node_id}`/`{document_id}` pattern it
# would otherwise also match.
# 🇧🇷 Ordenado do mais específico primeiro: um segmento literal (`complete`,
# `versions`) precisa ser tentado antes do padrão coringa `{node_id}`/`{document_id}`
# que também bateria nele.
NODE_ROUTES: list[tuple[re.Pattern[str], str, _RouteHandler]] = [
    (re.compile(rf"{_NODES}/uploads$"), "POST", _stage_nodes_route),
    (re.compile(rf"{_NODES}/uploads/complete$"), "POST", _complete_single_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart$"), "POST", _start_multipart_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart/parts$"), "POST", _sign_parts_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart/complete$"), "POST", _complete_multipart_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart/abort$"), "POST", _abort_multipart_route),
    (re.compile(rf"{_NODES}$"), "GET", _list_nodes_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)$"), "GET", _get_node_route),
]
