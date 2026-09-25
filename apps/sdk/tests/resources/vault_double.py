"""🇺🇸 A tiny in-memory vault + R2 double shared by every `resources/` test.

`FakeVault` is deliberately not a mock of `VaultTransport`'s methods — it is
a real `httpx.MockTransport` handler, plain Python dicts standing in for
Firestore and R2, so a bug in how `resources/` builds a request (a wrong
path, a missing field, a `content-length` that does not match the body it
sends) shows up as a real HTTP-shaped failure, the same way it would against
the vault. `Keyring`s in these tests are built by hand with known group DEKs
— the whole point of `resources/` is that it never invents keys of its own,
so a test that cannot supply a `Keyring` directly would be testing the
wrong layer.

🇧🇷 Um duplo minúsculo de cofre + R2 em memória, compartilhado por todo teste de `resources/`.

`FakeVault` de propósito não é um mock dos métodos de `VaultTransport` — é
um handler de `httpx.MockTransport` de verdade, dicts Python puros no lugar
do Firestore e do R2, para um bug em como `resources/` monta uma requisição
(um path errado, um campo faltando, um `content-length` que não bate com o
corpo que manda) aparecer como uma falha HTTP de verdade, do mesmo jeito que
apareceria contra o cofre. Os `Keyring`s destes testes são montados à mão
com DEKs de grupo conhecidas — o ponto inteiro de `resources/` é nunca
inventar chave própria, então um teste que não pudesse fornecer um `Keyring`
direto estaria testando a camada errada.

🇺🇸 Named `vault_double.py`, not `conftest.py`, on purpose: `apps/sdk/tests/conftest.py`
already claims the bare module name every test file imports from
(`from conftest import VECTORS`, `tests/transport/test_signing.py`), and a
second file also named `conftest.py` would collide with it the moment both
get imported under the same top-level name in the same test run. Every test
file here imports what it needs explicitly — `from vault_double import
Harness, harness, make_documents` — the same bare-import shape the rest of
the suite already uses, just against a different name.
🇧🇷 Chamado `vault_double.py`, não `conftest.py`, de propósito:
`apps/sdk/tests/conftest.py` já reivindica o nome de módulo cru que todo arquivo
de teste importa (`from conftest import VECTORS`,
`tests/transport/test_signing.py`), e um segundo arquivo também chamado
`conftest.py` colidiria com ele assim que os dois fossem importados sob o
mesmo nome de topo na mesma rodada de teste. Todo arquivo de teste aqui
importa o que precisa explicitamente — `from vault_double import Harness,
harness, make_documents` — o mesmo formato de import direto que o resto da
suíte já usa, só que contra um nome diferente.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
import pytest
from diagnos.crypto import EntropyMixer
from diagnos.crypto.secure import SecretBox
from diagnos.models import ResourceKind
from diagnos.resources._documents import VersionedDocuments
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.token import ServiceAccountToken
from pydantic import BaseModel

RecordT = TypeVar("RecordT", bound=BaseModel)

WORKSPACE_ID = "ws_1"
VAULT_URL = "https://vault.example.test"

# 🇺🇸 §13's `content_length` limit does not apply to this double — a huge
# `_DEFAULT_SINGLE_THRESHOLD` just means "everything is 'single' unless a
# test lowers it", mirroring `services/uploads`' own single-vs-multipart cutoff.
# 🇧🇷 O limite de `content_length` de §13 não vale para este duplo — um
# `_DEFAULT_SINGLE_THRESHOLD` enorme só significa "tudo é 'single' a menos
# que um teste o abaixe", espelhando o corte single-vs-multipart de `services/uploads`.
_DEFAULT_SINGLE_THRESHOLD = 1_000_000


def _time_response(request: httpx.Request) -> httpx.Response:
    """🇺🇸 The raw (unenveloped) shape `GET /time` answers with — same as `tests/transport/test_http.py`.

    🇧🇷 A forma crua (sem envelope) que `GET /time` responde — igual a `tests/transport/test_http.py`.
    """
    return httpx.Response(200, json={"result": 1_700_000_000_000})


def _envelope_success(result: object, status: int = 200) -> httpx.Response:
    """🇺🇸 A `success: true` envelope carrying `result`, `docs/PROTOCOL.md §0`.

    🇧🇷 Um envelope `success: true` carregando `result`, `docs/PROTOCOL.md §0`.
    """
    return httpx.Response(
        status,
        json={"success": True, "status": "success", "status_code": status, "result": result, "docs": "d"},
    )


def _envelope_error(code: str, *, status: int, message: str = "not found") -> httpx.Response:
    """🇺🇸 A `success: false` envelope carrying one error `code`, `docs/PROTOCOL.md §0`.

    🇧🇷 Um envelope `success: false` carregando um `code` de erro, `docs/PROTOCOL.md §0`.
    """
    return httpx.Response(
        status,
        json={
            "success": False,
            "status": "fail",
            "status_code": status,
            "errors": [{"code": code, "message": message, "trace_id": None}],
            "docs": "d",
        },
    )


@dataclass
class _PendingVersion:
    """🇺🇸 What `create`/`update` staged but has not yet `commit`-ted.

    🇧🇷 O que `create`/`update` reservou mas ainda não confirmou (`commit`).
    """

    version_id: str
    storage_key: str
    meta: dict[str, Any] | None
    is_archived: bool | None
    is_deleted: bool | None


class FakeVault:
    """🇺🇸 In-memory stand-in for the vault's documents/drives API plus R2 object storage.

    🇧🇷 Substituto em memória para a API de documentos/drives do cofre mais o armazenamento de objetos do R2.
    """

    def __init__(self) -> None:
        """🇺🇸 Starts empty; every test seeds only what it needs.

        🇧🇷 Começa vazio; cada teste semeia só o que precisa.
        """
        self._documents: dict[tuple[str, str], dict[str, Any]] = {}
        self._pending: dict[tuple[str, str], _PendingVersion] = {}
        self._nodes: dict[tuple[str, str], dict[str, Any]] = {}
        self._objects: dict[str, bytes] = {}
        self._parts: dict[tuple[str, int], bytes] = {}
        self._counter = 0
        self.single_threshold = _DEFAULT_SINGLE_THRESHOLD
        self.part_size = 32 * 1024 * 1024
        # 🇺🇸 Every `PUT` to storage, kept verbatim (headers included) so a test
        # can assert on `content-length`/SSE-C headers without needing its own
        # transport-level spy.
        # 🇧🇷 Todo `PUT` ao armazenamento, guardado ao pé da letra (headers
        # inclusos) para um teste assertar `content-length`/headers de SSE-C
        # sem precisar do próprio espião no nível de transporte.
        self.put_requests: list[httpx.Request] = []
        self.get_requests: list[httpx.Request] = []

    def _next_id(self, prefix: str) -> str:
        """🇺🇸 A short, readable, unique-enough id for this process's lifetime.

        🇧🇷 Um id curto, legível, único o bastante para a vida deste processo.
        """
        self._counter += 1
        return f"{prefix}_{self._counter}"

    # -- httpx.MockTransport handlers ---------------------------------------

    def handle_api(self, request: httpx.Request) -> httpx.Response:
        """🇺🇸 Routes one signed API call to the matching in-memory operation.

        🇧🇷 Roteia uma chamada de API assinada para a operação em memória correspondente.
        """
        if request.url.path == "/time":
            return _time_response(request)

        method = request.method
        path = request.url.path
        query = dict(request.url.params)
        body: dict[str, Any] = json.loads(request.content) if request.content else {}

        for pattern, allowed_method, handler in _ROUTES:
            if method != allowed_method:
                continue
            match = pattern.match(path)
            if match is None:
                continue
            try:
                return handler(self, match.groupdict(), query, body)
            except _NotFoundError as exc:
                return _envelope_error(exc.code, status=404, message=str(exc))

        raise AssertionError(f"FakeVault: no route for {method} {path}")

    def handle_storage(self, request: httpx.Request) -> httpx.Response:
        """🇺🇸 Routes a `PUT`/`GET` against a presigned R2 URL to the in-memory object store.

        🇧🇷 Roteia um `PUT`/`GET` contra uma URL presigned do R2 para o armazém de objetos em memória.
        """
        url = str(request.url)
        if request.method == "PUT":
            self._objects[url] = request.content
            self.put_requests.append(request)
            etag = f'"{secrets.token_hex(8)}"'
            return httpx.Response(200, headers={"ETag": etag})
        if request.method == "GET":
            self.get_requests.append(request)
            data = self._objects.get(url)
            if data is None:
                return httpx.Response(404)
            return httpx.Response(200, content=data)
        raise AssertionError(f"FakeVault: unexpected storage method {request.method}")

    # -- documents (patients/exams) ------------------------------------------

    def _object_url(self, key: str) -> str:
        """🇺🇸 A stable, opaque presigned-looking URL for one storage key.

        🇧🇷 Uma URL presigned opaca e estável para uma chave de armazenamento.
        """
        return f"https://r2.example.test/objects/{key}"

    def list_documents(
        self, resource: str, *, security_group_id: str | None, include_deleted: bool, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        """🇺🇸 All indexes of `resource`, filtered and paginated the way `GET {base}` promises.

        🇧🇷 Todo índice de `resource`, filtrado e paginado do jeito que `GET {base}` promete.
        """
        items = [
            index
            for (res, _document_id), index in self._documents.items()
            if res == resource and (include_deleted or not index["is_deleted"])
            if security_group_id is None or security_group_id in index["security_groups"]
        ]
        items.sort(key=lambda index: index["document_id"])
        start = 0
        if cursor is not None:
            start = next(i for i, index in enumerate(items) if index["document_id"] == cursor) + 1
        page = items[start : start + limit]
        next_cursor = page[-1]["document_id"] if start + limit < len(items) else None
        return {"items": page, "next_cursor": next_cursor}

    def create_document(self, resource: str, body: dict[str, Any]) -> dict[str, Any]:
        """🇺🇸 `POST {base}` — a brand new document with one pending version.

        🇧🇷 `POST {base}` — um documento novo com uma versão pendente.
        """
        document_id = self._next_id("doc")
        version_id = self._next_id("ver")
        storage_key = f"doc/{resource}/{document_id}/{version_id}"
        index = {
            "document_id": document_id,
            "workspace_id": WORKSPACE_ID,
            "resource": resource,
            "security_groups": body["security_groups"],
            "encrypted_keys": body["encrypted_keys"],
            "latest_version_id": None,
            "versions": [],
            "pending_version_id": version_id,
            "meta": body.get("meta") or {},
            "created_at": "2024-01-01T00:00:00Z",
            "created_by": "test-actor",
            "updated_at": "2024-01-01T00:00:00Z",
            "updated_by": "test-actor",
            "is_archived": False,
            "is_deleted": False,
        }
        self._documents[(resource, document_id)] = index
        self._pending[(resource, document_id)] = _PendingVersion(
            version_id=version_id, storage_key=storage_key, meta=None, is_archived=None, is_deleted=None
        )
        upload = {
            "url": self._object_url(storage_key),
            "method": "PUT",
            "headers": {"content-length": str(body["content_length"])},
            "expires_at": 9_999_999_999,
        }
        return {"document": dict(index), "version_id": version_id, "upload": upload}

    def stage_version(self, resource: str, document_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """🇺🇸 `POST {base}/{id}/versions` — a new pending version for an existing document.

        🇧🇷 `POST {base}/{id}/versions` — uma versão pendente nova para um documento existente.
        """
        key = (resource, document_id)
        if key not in self._documents:
            raise _NotFoundError("DocumentNotFound", document_id)
        version_id = self._next_id("ver")
        storage_key = f"doc/{resource}/{document_id}/{version_id}"
        self._pending[key] = _PendingVersion(
            version_id=version_id,
            storage_key=storage_key,
            meta=body.get("meta"),
            is_archived=body.get("is_archived"),
            is_deleted=body.get("is_deleted"),
        )
        index = dict(self._documents[key])
        index["pending_version_id"] = version_id
        upload = {
            "url": self._object_url(storage_key),
            "method": "PUT",
            "headers": {"content-length": str(body["content_length"])},
            "expires_at": 9_999_999_999,
        }
        return {"document": index, "version_id": version_id, "upload": upload}

    def commit_version(self, resource: str, document_id: str, version_id: str) -> dict[str, Any]:
        """🇺🇸 `POST {base}/{id}/versions/{version_id}/commit` — promotes the pending version to latest.

        🇧🇷 `POST {base}/{id}/versions/{version_id}/commit` — promove a versão pendente a mais recente.
        """
        key = (resource, document_id)
        pending = self._pending.get(key)
        if pending is None or pending.version_id != version_id:
            raise _NotFoundError("DocumentVersionNotFound", version_id)
        body_bytes = self._objects[self._object_url(pending.storage_key)]
        index = self._documents[key]
        index["latest_version_id"] = version_id
        index["versions"].append(
            {
                "version_id": version_id,
                "size": len(body_bytes),
                "created_at": "2024-01-01T00:00:00Z",
                "created_by": "test-actor",
            }
        )
        index["pending_version_id"] = None
        if pending.meta:
            index["meta"] = {**index["meta"], **pending.meta}
        if pending.is_archived is not None:
            index["is_archived"] = pending.is_archived
        if pending.is_deleted is not None:
            index["is_deleted"] = pending.is_deleted
        index["updated_at"] = "2024-01-02T00:00:00Z"
        del self._pending[key]
        return {"document": dict(index)}

    def get_document(self, resource: str, document_id: str, *, version_id: str | None) -> dict[str, Any]:
        """🇺🇸 `GET {base}/{id}` — the index plus a download URL for `version_id` (or latest).

        🇧🇷 `GET {base}/{id}` — o índice mais uma URL de download para `version_id` (ou a mais recente).
        """
        key = (resource, document_id)
        index = self._documents.get(key)
        if index is None:
            raise _NotFoundError("DocumentNotFound", document_id)
        target_version_id = version_id or index["latest_version_id"]
        version = next((v for v in index["versions"] if v["version_id"] == target_version_id), None)
        if version is None:
            raise _NotFoundError("DocumentVersionNotFound", str(target_version_id))
        storage_key = f"doc/{resource}/{document_id}/{target_version_id}"
        download = {"url": self._object_url(storage_key), "method": "GET", "expires_at": 9_999_999_999}
        return {"document": dict(index), "version": version, "download": download}

    # -- drives ---------------------------------------------------------------

    def stage_uploads(self, security_group_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """🇺🇸 `POST {base}/uploads` — reserves one node per file, single or multipart by size.

        🇧🇷 `POST {base}/uploads` — reserva um nó por arquivo, single ou multipart pelo tamanho.
        """
        exam_id = body.get("exam_id")
        nodes = []
        for file in body["files"]:
            node_id = self._next_id("node")
            size = file["size"]
            mode = "single" if size <= self.single_threshold else "multipart"
            storage_key = f"drive/{security_group_id}/{node_id}"
            node = {
                "node_id": node_id,
                "workspace_id": WORKSPACE_ID,
                "security_group_id": security_group_id,
                "exam_id": exam_id,
                "parent_id": None,
                "status": "pending",
                "mode": mode,
                "declared_size": size,
                "size": None,
                "mime_type": file.get("mime_type"),
                "media_kind": "other",
                "encrypted_name": file.get("encrypted_name"),
                "part_size": None,
                "part_count": None,
                "storage_path": storage_key,
                "created_by": "test-actor",
                "created_at": "2024-01-01T00:00:00Z",
                "completed_at": None,
            }
            self._nodes[(security_group_id, node_id)] = node
            if mode == "single":
                nodes.append(
                    {
                        "client_ref": file["client_ref"],
                        "node_id": node_id,
                        "mode": "single",
                        "upload": {
                            "url": self._object_url(storage_key),
                            "method": "PUT",
                            "headers": {"content-length": str(size)},
                            "expires_at": 9_999_999_999,
                        },
                    }
                )
            else:
                part_count = -(-size // self.part_size)  # 🇺🇸/🇧🇷 ceil division
                node["part_size"] = self.part_size
                node["part_count"] = part_count
                nodes.append(
                    {
                        "client_ref": file["client_ref"],
                        "node_id": node_id,
                        "mode": "multipart",
                        "part_size": self.part_size,
                        "part_count": part_count,
                    }
                )
        return {"nodes": nodes}

    def complete_single(self, security_group_id: str, node_ids: list[str]) -> dict[str, Any]:
        """🇺🇸 `POST {base}/uploads/complete` — 'ready' every node whose object actually landed.

        🇧🇷 `POST {base}/uploads/complete` — marca 'ready' todo nó cujo objeto de fato chegou.
        """
        ready = []
        missing = []
        for node_id in node_ids:
            node = self._nodes[(security_group_id, node_id)]
            data = self._objects.get(self._object_url(node["storage_path"]))
            if data is None:
                missing.append(node_id)
                continue
            node["status"] = "ready"
            node["size"] = len(data)
            node["completed_at"] = "2024-01-01T00:01:00Z"
            ready.append(dict(node))
        return {"ready": ready, "missing": missing}

    def start_multipart(self, security_group_id: str, node_id: str) -> dict[str, Any]:
        """🇺🇸 `POST {base}/uploads/{id}/multipart` — hands back the part plan `stage_uploads` already decided.

        🇧🇷 `POST {base}/uploads/{id}/multipart` — devolve o plano de partes que `stage_uploads` já decidiu.
        """
        node = self._nodes[(security_group_id, node_id)]
        return {"upload_id": self._next_id("mpu"), "part_size": node["part_size"], "part_count": node["part_count"]}

    def sign_parts(self, security_group_id: str, node_id: str, part_numbers: list[int]) -> dict[str, Any]:
        """🇺🇸 `POST {base}/uploads/{id}/multipart/parts` — one presigned `PUT` URL per requested part number.

        🇧🇷 `POST {base}/uploads/{id}/multipart/parts` — uma URL de `PUT` presigned por número de parte pedido.
        """
        parts = [
            {
                "part_number": number,
                "url": f"https://r2.example.test/parts/{node_id}/{number}",
                "expires_at": 9_999_999_999,
            }
            for number in part_numbers
        ]
        return {"parts": parts}

    def complete_multipart(self, security_group_id: str, node_id: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        """🇺🇸 `POST {base}/uploads/{id}/multipart/complete` — concatenates every part, in order, into the final object.

        🇧🇷 `POST {base}/uploads/{id}/multipart/complete` — concatena toda parte, em ordem, no objeto final.
        """
        node = self._nodes[(security_group_id, node_id)]
        ordered = sorted(parts, key=lambda p: p["part_number"])
        assembled = b"".join(
            self._objects[f"https://r2.example.test/parts/{node_id}/{part['part_number']}"] for part in ordered
        )
        self._objects[self._object_url(node["storage_path"])] = assembled
        node["status"] = "ready"
        node["size"] = len(assembled)
        node["completed_at"] = "2024-01-01T00:01:00Z"
        return {"node": dict(node)}

    def list_nodes(
        self, security_group_id: str, *, exam_id: str | None, include_pending: bool, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        """🇺🇸 `GET {base}/nodes` — every node of the drive, filtered and paginated.

        🇧🇷 `GET {base}/nodes` — todo nó do drive, filtrado e paginado.
        """
        items = [
            node
            for (sg, _node_id), node in self._nodes.items()
            if sg == security_group_id and (include_pending or node["status"] == "ready")
            if exam_id is None or node["exam_id"] == exam_id
        ]
        items.sort(key=lambda node: node["node_id"])
        start = 0
        if cursor is not None:
            start = next(i for i, node in enumerate(items) if node["node_id"] == cursor) + 1
        page = items[start : start + limit]
        next_cursor = page[-1]["node_id"] if start + limit < len(items) else None
        return {"items": page, "next_cursor": next_cursor}

    def get_node(self, security_group_id: str, node_id: str) -> dict[str, Any]:
        """🇺🇸 `GET {base}/nodes/{id}` — the node plus a download URL for its assembled object.

        🇧🇷 `GET {base}/nodes/{id}` — o nó mais uma URL de download do objeto montado.
        """
        node = self._nodes.get((security_group_id, node_id))
        if node is None:
            raise _NotFoundError("DriveNodeNotFound", node_id)
        download = {"url": self._object_url(node["storage_path"]), "method": "GET", "expires_at": 9_999_999_999}
        return {"node": dict(node), "download": download}


class _NotFoundError(Exception):
    """🇺🇸 Internal signal from a `FakeVault` operation to `handle_api`: turn this into a 404 envelope.

    🇧🇷 Sinal interno de uma operação de `FakeVault` para `handle_api`: transforme isto num envelope 404.
    """

    def __init__(self, code: str, detail: str) -> None:
        """🇺🇸 `code` is the vault error code (`docs/PROTOCOL.md §12`); `detail` is just for the message.

        🇧🇷 `code` é o código de erro do cofre (`docs/PROTOCOL.md §12`); `detail` é só para a mensagem.
        """
        super().__init__(detail)
        self.code = code


_RouteHandler = Callable[[FakeVault, dict[str, str], dict[str, str], dict[str, Any]], httpx.Response]


def _list_documents_route(
    vault: FakeVault, groups: dict[str, str], query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET {base}` for patients/exams. 🇧🇷 `GET {base}` de pacientes/exames."""
    result = vault.list_documents(
        groups["resource"],
        security_group_id=query.get("security_group_id"),
        include_deleted=query.get("include_deleted") == "true",
        limit=int(query.get("limit", 50)),
        cursor=query.get("cursor"),
    )
    return _envelope_success(result)


def _create_document_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}` for patients/exams. 🇧🇷 `POST {base}` de pacientes/exames."""
    return _envelope_success(vault.create_document(groups["resource"], body), status=201)


def _get_document_route(
    vault: FakeVault, groups: dict[str, str], query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET {base}/{document_id}`. 🇧🇷 `GET {base}/{document_id}`."""
    result = vault.get_document(groups["resource"], groups["document_id"], version_id=query.get("version_id"))
    return _envelope_success(result)


def _stage_version_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}/{document_id}/versions`. 🇧🇷 `POST {base}/{document_id}/versions`."""
    result = vault.stage_version(groups["resource"], groups["document_id"], body)
    return _envelope_success(result, status=201)


def _commit_version_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}/{document_id}/versions/{version_id}/commit`.

    🇧🇷 `POST {base}/{document_id}/versions/{version_id}/commit`.
    """
    result = vault.commit_version(groups["resource"], groups["document_id"], groups["version_id"])
    return _envelope_success(result)


def _stage_uploads_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}/uploads`. 🇧🇷 `POST {base}/uploads`."""
    return _envelope_success(vault.stage_uploads(groups["security_group_id"], body), status=201)


def _complete_single_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}/uploads/complete`. 🇧🇷 `POST {base}/uploads/complete`."""
    return _envelope_success(vault.complete_single(groups["security_group_id"], body["node_ids"]))


def _start_multipart_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}/uploads/{node_id}/multipart`. 🇧🇷 `POST {base}/uploads/{node_id}/multipart`."""
    return _envelope_success(vault.start_multipart(groups["security_group_id"], groups["node_id"]))


def _sign_parts_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}/uploads/{node_id}/multipart/parts`. 🇧🇷 `POST {base}/uploads/{node_id}/multipart/parts`."""
    result = vault.sign_parts(groups["security_group_id"], groups["node_id"], body["part_numbers"])
    return _envelope_success(result)


def _complete_multipart_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST {base}/uploads/{node_id}/multipart/complete`. 🇧🇷 `POST {base}/uploads/{node_id}/multipart/complete`."""
    result = vault.complete_multipart(groups["security_group_id"], groups["node_id"], body["parts"])
    return _envelope_success(result)


def _list_nodes_route(
    vault: FakeVault, groups: dict[str, str], query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET {base}/nodes`. 🇧🇷 `GET {base}/nodes`."""
    result = vault.list_nodes(
        groups["security_group_id"],
        exam_id=query.get("exam_id"),
        include_pending=query.get("include_pending") == "true",
        limit=int(query.get("limit", 50)),
        cursor=query.get("cursor"),
    )
    return _envelope_success(result)


def _get_node_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET {base}/nodes/{node_id}`. 🇧🇷 `GET {base}/nodes/{node_id}`."""
    result = vault.get_node(groups["security_group_id"], groups["node_id"])
    return _envelope_success(result)


_WS = WORKSPACE_ID
# 🇺🇸 Ordered most-specific-first: a literal segment (`complete`, `versions`)
# must be tried before the catch-all `{node_id}`/`{document_id}` pattern it
# would otherwise also match.
# 🇧🇷 Ordenado do mais específico primeiro: um segmento literal (`complete`,
# `versions`) precisa ser tentado antes do padrão coringa `{node_id}`/`{document_id}`
# que também bateria nele.
_ROUTES: list[tuple[re.Pattern[str], str, _RouteHandler]] = [
    (re.compile(rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients|exams)$"), "GET", _list_documents_route),
    (re.compile(rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients|exams)$"), "POST", _create_document_route),
    (
        re.compile(
            rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients|exams)/(?P<document_id>[^/]+)/versions$"
        ),
        "POST",
        _stage_version_route,
    ),
    (
        re.compile(
            rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients|exams)/(?P<document_id>[^/]+)"
            r"/versions/(?P<version_id>[^/]+)/commit$"
        ),
        "POST",
        _commit_version_route,
    ),
    (
        re.compile(rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients|exams)/(?P<document_id>[^/]+)$"),
        "GET",
        _get_document_route,
    ),
    (
        re.compile(rf"^/api/external/v1/workspaces/{_WS}/drives/(?P<security_group_id>[^/]+)/uploads$"),
        "POST",
        _stage_uploads_route,
    ),
    (
        re.compile(rf"^/api/external/v1/workspaces/{_WS}/drives/(?P<security_group_id>[^/]+)/uploads/complete$"),
        "POST",
        _complete_single_route,
    ),
    (
        re.compile(
            rf"^/api/external/v1/workspaces/{_WS}/drives/(?P<security_group_id>[^/]+)/uploads/(?P<node_id>[^/]+)/multipart$"
        ),
        "POST",
        _start_multipart_route,
    ),
    (
        re.compile(
            rf"^/api/external/v1/workspaces/{_WS}/drives/(?P<security_group_id>[^/]+)"
            r"/uploads/(?P<node_id>[^/]+)/multipart/parts$"
        ),
        "POST",
        _sign_parts_route,
    ),
    (
        re.compile(
            rf"^/api/external/v1/workspaces/{_WS}/drives/(?P<security_group_id>[^/]+)"
            r"/uploads/(?P<node_id>[^/]+)/multipart/complete$"
        ),
        "POST",
        _complete_multipart_route,
    ),
    (
        re.compile(rf"^/api/external/v1/workspaces/{_WS}/drives/(?P<security_group_id>[^/]+)/nodes$"),
        "GET",
        _list_nodes_route,
    ),
    (
        re.compile(
            rf"^/api/external/v1/workspaces/{_WS}/drives/(?P<security_group_id>[^/]+)/nodes/(?P<node_id>[^/]+)$"
        ),
        "GET",
        _get_node_route,
    ),
]


def _fresh_session_keys() -> SessionKeys:
    """🇺🇸 A session valid far into the future — none of these tests exercise expiry.

    Each key is born as its own `SecretBox` (`from_bytes` on a fresh
    `bytearray`, not a `bytes` literal) so the box holds the only copy — no
    caller can zero the underlying buffer out from under a later `as_secret`.

    🇧🇷 Uma sessão válida bem no futuro — nenhum destes testes exercita expiração.

    Cada chave nasce em seu próprio `SecretBox` (`from_bytes` sobre um
    `bytearray` novo, não um literal `bytes`) para a caixa guardar a única
    cópia — nenhum chamador consegue zerar o buffer por baixo de um
    `as_secret` posterior.
    """
    return SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        enc_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        expires_at=9_999_999_999,
    )


def make_keyring(group_deks: dict[str, bytes]) -> Keyring:
    """🇺🇸 A `Keyring` holding exactly the group DEKs a test supplies — no enrollment, no network.

    Each DEK becomes its own `SecretBox`, born from a copy of the input
    bytes (`bytearray(dek)`) so the caller's own `bytes` — often reused
    across assertions in the same test — is never the buffer that gets
    zeroed.

    🇧🇷 Um `Keyring` com exatamente as DEKs de grupo que um teste fornece — sem enrollment, sem rede.

    Cada DEK vira seu próprio `SecretBox`, nascido de uma cópia dos bytes de
    entrada (`bytearray(dek)`) para o `bytes` do chamador — muitas vezes
    reusado em outras asserções do mesmo teste — nunca ser o buffer zerado.
    """
    return Keyring(
        enrollment_id="enroll_1",
        session=_fresh_session_keys(),
        group_keys={sg: SecretBox.from_bytes(bytearray(dek)) for sg, dek in group_deks.items()},
    )


@dataclass
class Harness:
    """🇺🇸 Everything a `resources/` test needs: the fake backend, a live `VaultTransport`, entropy, keyring.

    🇧🇷 Tudo que um teste de `resources/` precisa: o backend falso, um `VaultTransport` vivo, entropia, keyring.
    """

    vault: FakeVault
    transport: VaultTransport
    entropy: EntropyMixer
    keyring: Keyring
    settings: Settings

    def keyring_provider(self) -> Keyring:
        """🇺🇸 The callable shape `VersionedDocuments`/`Drive` expect for `keyring_provider`.

        🇧🇷 A forma de callable que `VersionedDocuments`/`Drive` esperam para `keyring_provider`.
        """
        return self.keyring


def _default_group_deks() -> dict[str, bytes]:
    """🇺🇸 Two named security groups with fresh, independent DEKs.

    A plain function, not a fixture: `harness`/`sse_c_harness` are the only
    fixtures a test file needs to import (`docs/README.md`'s bare-import
    convention — see the module docstring), and each calls this on its own
    rather than depending on a `group_deks` fixture that a test module
    importing only `harness` would never register.

    🇧🇷 Dois security groups nomeados com DEKs novas e independentes.

    Uma função simples, não uma fixture: `harness`/`sse_c_harness` são as
    únicas fixtures que um arquivo de teste precisa importar (convenção de
    import direto — ver a docstring do módulo), e cada uma chama isto por
    conta própria em vez de depender de uma fixture `group_deks` que um
    módulo de teste importando só `harness` nunca registraria.
    """
    return {"sg1": secrets.token_bytes(32), "sg2": secrets.token_bytes(32)}


@pytest.fixture
def harness() -> Harness:
    """🇺🇸 A ready-to-use `Harness`, `sse_c` off by default.

    🇧🇷 Um `Harness` pronto para uso, `sse_c` desligado por padrão.
    """
    return _build_harness(_default_group_deks(), sse_c=False)


@pytest.fixture
def sse_c_harness() -> Harness:
    """🇺🇸 The same harness with `sse_c` on, for the SSE-C header assertions.

    🇧🇷 O mesmo harness com `sse_c` ligado, para as asserções de headers de SSE-C.
    """
    return _build_harness(_default_group_deks(), sse_c=True)


def _build_harness(group_deks: dict[str, bytes], *, sse_c: bool) -> Harness:
    """🇺🇸 Wires a fresh `FakeVault` to a real `VaultTransport` over `httpx.MockTransport`.

    🇧🇷 Conecta um `FakeVault` novo a um `VaultTransport` de verdade sobre `httpx.MockTransport`.
    """
    vault = FakeVault()
    keyring = make_keyring(group_deks)
    settings = Settings(api_token="apikey-test", vault_url=VAULT_URL, sse_c=sse_c)  # noqa: S106 — test fixture, not a real secret
    api_client = httpx.Client(transport=httpx.MockTransport(vault.handle_api), base_url=VAULT_URL)
    storage_client = httpx.Client(transport=httpx.MockTransport(vault.handle_storage))
    entropy = EntropyMixer()
    transport = VaultTransport(
        settings,
        _token(),
        session_keys=lambda: keyring.session,
        client=api_client,
        storage_client=storage_client,
    )
    return Harness(vault=vault, transport=transport, entropy=entropy, keyring=keyring, settings=settings)


def _token() -> ServiceAccountToken:
    """🇺🇸 A `ServiceAccountToken` for `WORKSPACE_ID`, built without a real JWT.

    🇧🇷 Um `ServiceAccountToken` para `WORKSPACE_ID`, montado sem um JWT de verdade.
    """
    return ServiceAccountToken(
        raw="apikey-test",
        key_id="key_1",
        account_id="acc_1",
        workspace_id=WORKSPACE_ID,
        name=f"svc@{WORKSPACE_ID}.diagnos.health",
    )


def make_documents(
    harness: Harness, *, resource: ResourceKind, record_model: type[RecordT]
) -> VersionedDocuments[RecordT]:
    """🇺🇸 A `VersionedDocuments` wired to `harness`, for `test_documents.py` to exercise the engine directly.

    🇧🇷 Um `VersionedDocuments` conectado a `harness`, para `test_documents.py` exercitar o motor direto.
    """
    return VersionedDocuments(
        harness.transport,
        harness.keyring_provider,
        harness.entropy,
        workspace_id=WORKSPACE_ID,
        resource=resource,
        record_model=record_model,
        settings=harness.settings,
    )
