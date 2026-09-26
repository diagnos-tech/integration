"""🇺🇸 A tiny in-memory vault + R2 double shared by every `resources/` test.

`FakeVault` is deliberately not a mock of `VaultTransport`'s methods — it is
a real `httpx.MockTransport` handler, plain Python dicts standing in for
Firestore and R2, so a bug in how `resources/` builds a request (a wrong
path, a missing field, a `content-length` that does not match the body it
sends) shows up as a real HTTP-shaped failure, the same way it would against
the vault. The document half follows `routes/factories/versionedDocuments.ts`
and `services/documents/store.ts` rule for rule: stream-aware paths, the
singular `security_group_id`, required `encrypted_index`, a signed `PUT`
locked to the declared size, one pending slot per stream, patch-only
reservations, `expected_latest_version_id`, and the draft head. `Keyring`s
in these tests are built by hand with known group keys — the whole point of
`resources/` is that it never invents keys of its own.

🇧🇷 Um duplo minúsculo de cofre + R2 em memória, compartilhado por todo teste de `resources/`.

`FakeVault` de propósito não é um mock dos métodos de `VaultTransport` — é
um handler de `httpx.MockTransport` de verdade, dicts Python puros no lugar
do Firestore e do R2, para um bug em como `resources/` monta uma requisição
(um path errado, um campo faltando, um `content-length` que não bate com o
corpo que manda) aparecer como uma falha HTTP de verdade, do mesmo jeito que
apareceria contra o cofre. A metade de documentos segue
`routes/factories/versionedDocuments.ts` e `services/documents/store.ts`
regra por regra: paths cientes de fluxo, `security_group_id` no singular,
`encrypted_index` obrigatório, `PUT` assinado travado no tamanho declarado,
um slot pendente por fluxo, reservas só de patch,
`expected_latest_version_id` e a cabeça de rascunho. Os `Keyring`s destes
testes são montados à mão com chaves de grupo conhecidas — o ponto inteiro
de `resources/` é nunca inventar chave própria.

🇺🇸 Named `vault_double.py`, not `conftest.py`, on purpose: `apps/sdk/tests/conftest.py`
already claims the bare module name every test file imports from
(`from conftest import VECTORS`), and a second file also named `conftest.py`
would collide with it the moment both get imported under the same top-level
name in the same test run.
🇧🇷 Chamado `vault_double.py`, não `conftest.py`, de propósito:
`apps/sdk/tests/conftest.py` já reivindica o nome de módulo cru que todo arquivo
de teste importa (`from conftest import VECTORS`), e um segundo arquivo também
chamado `conftest.py` colidiria com ele assim que os dois fossem importados
sob o mesmo nome de topo na mesma rodada de teste.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
SummaryT = TypeVar("SummaryT", bound=BaseModel)

WORKSPACE_ID = "ws_1"
VAULT_URL = "https://vault.example.test"
ACTOR = "svc_test"

# 🇺🇸 §13's `content_length` limit does not apply to this double — a huge
# `_DEFAULT_SINGLE_THRESHOLD` just means "everything is 'single' unless a
# test lowers it", mirroring `services/uploads`' own single-vs-multipart cutoff.
# 🇧🇷 O limite de `content_length` de §13 não vale para este duplo — um
# `_DEFAULT_SINGLE_THRESHOLD` enorme só significa "tudo é 'single' a menos
# que um teste o abaixe", espelhando o corte single-vs-multipart de `services/uploads`.
_DEFAULT_SINGLE_THRESHOLD = 1_000_000

_STREAMS: dict[str, tuple[str, ...]] = {"patients": ("data", "file"), "exams": ("data",), "templates": ("data",)}
_REQUIRES_ENCRYPTED_INDEX = frozenset({"patients", "templates"})
_SSE_C_ALGORITHM_HEADER = "x-amz-server-side-encryption-customer-algorithm"
_SSE_C_CLIENT_HEADERS = ["x-amz-server-side-encryption-customer-key", "x-amz-server-side-encryption-customer-key-md5"]
_CREATE_FIELDS = frozenset(
    {"security_group_id", "encrypted_keys", "content_length", "stream", "meta", "encrypted_index"}
)
_STAGE_FIELDS = frozenset(
    {"content_length", "meta", "is_archived", "is_deleted", "encrypted_index", "expected_latest_version_id"}
)


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


class _VaultRefusal(Exception):  # noqa: N818 — a control-flow signal inside the fake, not an error type
    """🇺🇸 Internal signal from a `FakeVault` operation to `handle_api`: answer with this error envelope.

    🇧🇷 Sinal interno de uma operação de `FakeVault` para `handle_api`: responda com este envelope de erro.
    """

    def __init__(self, code: str, detail: str, *, status: int = 404) -> None:
        """🇺🇸 `code`/`status` as the vault sends them; `detail` is just for the message.

        🇧🇷 `code`/`status` como o cofre os manda; `detail` é só para a mensagem.
        """
        super().__init__(detail)
        self.code = code
        self.status = status


# 🇺🇸 Kept under its old name for the drive half, which only ever raises 404s.
# 🇧🇷 Mantido sob o nome antigo para a metade de drives, que só lança 404.
_NotFoundError = _VaultRefusal


_INVALID_SSE_C = object()


def _sse_c_key_of(request: httpx.Request) -> object:
    """🇺🇸 The request's SSE-C key (`None` without one); `_INVALID_SSE_C` when the trio is incomplete or wrong.

    🇧🇷 A chave de SSE-C da requisição (`None` sem ela); `_INVALID_SSE_C` quando o trio está incompleto ou errado.
    """
    algorithm = request.headers.get("x-amz-server-side-encryption-customer-algorithm")
    key = request.headers.get("x-amz-server-side-encryption-customer-key")
    md5 = request.headers.get("x-amz-server-side-encryption-customer-key-md5")
    if algorithm is None and key is None and md5 is None:
        return None
    if algorithm != "AES256" or key is None or md5 is None:
        return _INVALID_SSE_C
    raw = base64.b64decode(key)
    expected = base64.b64encode(hashlib.md5(raw, usedforsecurity=False).digest()).decode("ascii")
    return key if len(raw) == 32 and md5 == expected else _INVALID_SSE_C


@dataclass
class _Pending:
    """🇺🇸 A reserved version of one stream, not yet committed, plus the patch that rides with it.

    🇧🇷 Uma versão reservada de um fluxo, ainda não confirmada, mais o patch que viaja com ela.
    """

    version_id: str
    size: int
    patch: dict[str, Any] = field(default_factory=dict)


class FakeVault:
    """🇺🇸 In-memory stand-in for the vault's documents/drives API plus R2 object storage.

    🇧🇷 Substituto em memória para a API de documentos/drives do cofre mais o armazenamento de objetos do R2.
    """

    def __init__(self) -> None:
        """🇺🇸 Starts empty; every test seeds only what it needs.

        🇧🇷 Começa vazio; cada teste semeia só o que precisa.
        """
        self._documents: dict[tuple[str, str], dict[str, Any]] = {}
        self._pending: dict[tuple[str, str, str], _Pending] = {}
        self._nodes: dict[str, dict[str, Any]] = {}
        self._refs: dict[str, str] = {}
        self._multipart: dict[str, dict[str, Any]] = {}
        # 🇺🇸 The SSE-C key each stored object was written with (`None` = none), as R2 remembers its MD5.
        # 🇧🇷 A chave de SSE-C com que cada objeto foi gravado (`None` = nenhuma), como o R2 lembra o MD5.
        self._sse_keys: dict[str, str | None] = {}
        self._objects: dict[str, bytes] = {}
        self._signed_sizes: dict[str, int] = {}
        self._counter = 0
        self._clock = datetime(2026, 9, 1, tzinfo=UTC)
        self.single_threshold = _DEFAULT_SINGLE_THRESHOLD
        self.part_size = 32 * 1024 * 1024
        # 🇺🇸 Whether the batch reservation opens multipart uploads itself (the vault does; older ones did not).
        # 🇧🇷 Se a reserva do lote abre o multipart sozinha (o cofre abre; versões antigas não abriam).
        self.inline_multipart = True
        self.stage_calls = 0
        self.signed_part_batches: list[list[int]] = []
        self.aborted: list[str] = []
        # 🇺🇸 A test sets this to make the next N commits fail with a 503, as a flaky network would.
        # 🇧🇷 Um teste define isto para os próximos N commits falharem com 503, como uma rede instável.
        self.fail_next_commits = 0
        # 🇺🇸 Every API request and every storage `PUT`/`GET`, kept verbatim for assertions.
        # 🇧🇷 Toda requisição de API e todo `PUT`/`GET` de armazenamento, guardados ao pé da letra.
        self.api_requests: list[httpx.Request] = []
        self.put_requests: list[httpx.Request] = []
        self.get_requests: list[httpx.Request] = []

    def _next_id(self, prefix: str) -> str:
        """🇺🇸 A short, readable, unique-enough id for this process's lifetime.

        🇧🇷 Um id curto, legível, único o bastante para a vida deste processo.
        """
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def now(self) -> str:
        """🇺🇸 A strictly increasing server clock, one second per call, as ISO strings.

        🇧🇷 Um relógio de servidor estritamente crescente, um segundo por chamada, em strings ISO.
        """
        self._clock += timedelta(seconds=1)
        return self._clock.isoformat().replace("+00:00", ".000Z")

    # -- httpx.MockTransport handlers ---------------------------------------

    def handle_api(self, request: httpx.Request) -> httpx.Response:
        """🇺🇸 Routes one signed API call to the matching in-memory operation.

        🇧🇷 Roteia uma chamada de API assinada para a operação em memória correspondente.
        """
        if request.url.path == "/time":
            return _time_response(request)
        self.api_requests.append(request)

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
            except _VaultRefusal as exc:
                return _envelope_error(exc.code, status=exc.status, message=str(exc))

        raise AssertionError(f"FakeVault: no route for {method} {path}")

    def handle_storage(self, request: httpx.Request) -> httpx.Response:
        """🇺🇸 A `PUT`/`GET` against a presigned R2 URL, with R2's rules for size and SSE-C.

        A `PUT` must match the size the URL was signed for; an SSE-C key must
        match its MD5; a `GET` must present the same SSE-C key the object was
        written with (or none, if none) — R2 answers `400` otherwise.

        🇧🇷 Um `PUT`/`GET` contra uma URL pré-assinada do R2, com as regras do R2 para tamanho e SSE-C.

        Um `PUT` precisa bater com o tamanho assinado; uma chave de SSE-C
        precisa bater com o MD5 dela; um `GET` precisa apresentar a mesma
        chave de SSE-C com que o objeto foi gravado (ou nenhuma, se nenhuma)
        — o R2 responde `400` do contrário.
        """
        url = str(request.url)
        sse_key = _sse_c_key_of(request)
        if sse_key is _INVALID_SSE_C:
            return httpx.Response(400)
        if request.method == "PUT":
            self.put_requests.append(request)
            signed = self._signed_sizes.get(url)
            if signed is not None and signed != len(request.content):
                return httpx.Response(403)
            self._objects[url] = request.content
            self._sse_keys[url] = sse_key  # type: ignore[assignment]
            etag = f'"{secrets.token_hex(8)}"'
            return httpx.Response(200, headers={"ETag": etag})
        if request.method == "GET":
            self.get_requests.append(request)
            data = self._objects.get(url)
            if data is None:
                return httpx.Response(404)
            if self._sse_keys.get(url) != sse_key:
                return httpx.Response(400)
            return httpx.Response(200, content=data)
        raise AssertionError(f"FakeVault: unexpected storage method {request.method}")

    # -- documents (patients/exams/templates) --------------------------------

    def _object_url(self, key: str) -> str:
        """🇺🇸 A stable, opaque presigned-looking URL for one storage key.

        🇧🇷 Uma URL presigned opaca e estável para uma chave de armazenamento.
        """
        return f"https://storage.diagnosusercontent.com/objects/{key}"

    @staticmethod
    def security_context(resource: str, document_id: str, key_id: str) -> dict[str, str]:
        """🇺🇸 The deterministic `security_context` of one object — a test can derive the same content key.

        🇧🇷 O `security_context` determinístico de um objeto — um teste consegue derivar a mesma chave de conteúdo.
        """
        raw = f"ctx|{WORKSPACE_ID}|{resource}|{document_id}|{key_id}".encode()
        return {"value": base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"), "kid": "ctx_k1"}

    def version_url(self, resource: str, version_id: str) -> str:
        """🇺🇸 Where a version's object lives (flat by `version_id`, as in R2). 🇧🇷 Onde mora o objeto de uma versão."""
        return self._object_url(f"workspaces/{WORKSPACE_ID}/{resource}/{version_id}")

    def draft_url(self, resource: str, document_id: str, stream: str) -> str:
        """🇺🇸 Where a stream's draft head lives. 🇧🇷 Onde mora a cabeça de rascunho de um fluxo."""
        suffix = f"/{stream}" if len(_STREAMS[resource]) > 1 else ""
        return self._object_url(f"workspaces/{WORKSPACE_ID}/{resource}/{document_id}/draft{suffix}")

    def _signed_upload(self, url: str, size: int) -> dict[str, Any]:
        """🇺🇸 `SignedUploadResponse`: the size is locked into the URL; SSE-C names ride alongside.

        🇧🇷 `SignedUploadResponse`: o tamanho fica travado na URL; os nomes de SSE-C vão junto.
        """
        self._signed_sizes[url] = size
        return {
            "url": url,
            "method": "PUT",
            "headers": {"content-length": str(size), _SSE_C_ALGORITHM_HEADER: "AES256"},
            "client_headers": list(_SSE_C_CLIENT_HEADERS),
            "expires_at": 9_999_999_999,
        }

    @staticmethod
    def _signed_download(url: str) -> dict[str, Any]:
        """🇺🇸 `SignedDownloadResponse`. 🇧🇷 `SignedDownloadResponse`."""
        return {
            "url": url,
            "method": "GET",
            "headers": {_SSE_C_ALGORITHM_HEADER: "AES256"},
            "client_headers": list(_SSE_C_CLIENT_HEADERS),
            "expires_at": 9_999_999_999,
        }

    def _index(self, resource: str, document_id: str) -> dict[str, Any]:
        """🇺🇸 The stored index, or `DocumentNotFound`. 🇧🇷 O índice guardado, ou `DocumentNotFound`."""
        index = self._documents.get((resource, document_id))
        if index is None:
            raise _VaultRefusal("DocumentNotFound", document_id)
        return index

    def _response(self, resource: str, document_id: str) -> dict[str, Any]:
        """🇺🇸 `documentIndexResponse`: `pending_version_id` as an id only, streams always as a map.

        🇧🇷 `documentIndexResponse`: `pending_version_id` só como id, fluxos sempre como mapa.
        """
        index = self._documents[(resource, document_id)]
        streams = {}
        for name, stream in index["streams"].items():
            pending = self._pending.get((resource, document_id, name))
            entry = {
                "latest_version_id": stream["latest_version_id"],
                "versions": [dict(v) for v in stream["versions"]],
                "pending_version_id": pending.version_id if pending else None,
            }
            if stream.get("draft") is not None:
                entry["draft"] = dict(stream["draft"])
            streams[name] = entry
        response = {key: value for key, value in index.items() if key != "streams"}
        response["streams"] = streams
        return json.loads(json.dumps(response))

    def list_documents(
        self, resource: str, *, security_group_id: str | None, include_deleted: bool, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        """🇺🇸 All indexes of `resource`, filtered and paginated the way `GET {base}` promises.

        🇧🇷 Todo índice de `resource`, filtrado e paginado do jeito que `GET {base}` promete.
        """
        ids = sorted(
            document_id
            for (res, document_id), index in self._documents.items()
            if res == resource and (include_deleted or not index["is_deleted"])
            if security_group_id is None or index["security_group_id"] == security_group_id
        )
        start = ids.index(cursor) + 1 if cursor is not None else 0
        page = ids[start : start + limit]
        next_cursor = page[-1] if start + limit < len(ids) else None
        return {"items": [self._response(resource, document_id) for document_id in page], "next_cursor": next_cursor}

    def create_document(self, resource: str, body: dict[str, Any]) -> dict[str, Any]:
        """🇺🇸 `POST {base}` — `createDocumentRequest` validation, then a new index with one pending version.

        🇧🇷 `POST {base}` — validação de `createDocumentRequest`, depois um índice novo com uma versão pendente.
        """
        unknown = set(body) - _CREATE_FIELDS
        if unknown:
            raise _VaultRefusal("ValidationError", f"unknown fields {sorted(unknown)}", status=400)
        group = body.get("security_group_id")
        if not isinstance(group, str) or not group:
            raise _VaultRefusal("ValidationError", "security_group_id is required", status=400)
        if group not in body.get("encrypted_keys", {}):
            raise _VaultRefusal("ValidationError", "encrypted_keys must hold the DEK for security_group_id", status=400)
        if resource in _REQUIRES_ENCRYPTED_INDEX and "encrypted_index" not in body:
            raise _VaultRefusal("ValidationError", "encrypted_index is required for this resource", status=400)
        size = body.get("content_length")
        if not isinstance(size, int) or size <= 0:
            raise _VaultRefusal("ValidationError", "content_length must be a positive integer", status=400)
        stream = body.get("stream", "data") if len(_STREAMS[resource]) > 1 else "data"

        document_id = self._next_id("doc")
        version_id = self._next_id("ver")
        now = self.now()
        index: dict[str, Any] = {
            "document_id": document_id,
            "workspace_id": WORKSPACE_ID,
            "resource": resource,
            "security_group_id": group,
            "encrypted_keys": body["encrypted_keys"],
            "streams": {name: {"latest_version_id": None, "versions": []} for name in _STREAMS[resource]},
            "created_at": now,
            "created_by": ACTOR,
            "updated_at": now,
            "updated_by": ACTOR,
            "is_archived": False,
            "is_deleted": False,
        }
        if "encrypted_index" in body:
            index["encrypted_index"] = body["encrypted_index"]
        if body.get("meta") is not None:
            index["meta"] = body["meta"]
        self._documents[(resource, document_id)] = index
        self._pending[(resource, document_id, stream)] = _Pending(version_id=version_id, size=size)
        return {
            "document": self._response(resource, document_id),
            "stream": stream,
            "version_id": version_id,
            "security_context": self.security_context(resource, document_id, version_id),
            "upload": self._signed_upload(self.version_url(resource, version_id), size),
        }

    def stage_version(self, resource: str, document_id: str, stream: str, body: dict[str, Any]) -> dict[str, Any]:
        """🇺🇸 `POST .../versions` — a patch-only flag flip, or a new pending version (409 while one is open).

        🇧🇷 `POST .../versions` — uma troca de flag só-patch, ou uma versão pendente nova (409 com uma aberta).
        """
        unknown = set(body) - _STAGE_FIELDS
        if unknown:
            raise _VaultRefusal("ValidationError", f"unknown fields {sorted(unknown)}", status=400)
        index = self._index(resource, document_id)
        size = body.get("content_length")
        patch = {key: body[key] for key in ("meta", "is_archived", "is_deleted", "encrypted_index") if key in body}
        if size is None:
            if "meta" in patch or "encrypted_index" in patch or not {"is_archived", "is_deleted"} & set(patch):
                raise _VaultRefusal("ValidationError", "content_length is required", status=400)
            index.update(patch)
            index["updated_at"] = self.now()
            return {"staged": False, "document": self._response(resource, document_id)}

        expected = body.get("expected_latest_version_id")
        if expected is not None and expected != index["streams"][stream]["latest_version_id"]:
            raise _VaultRefusal("DocumentVersionMismatch", "another version was committed", status=409)
        if (resource, document_id, stream) in self._pending:
            raise _VaultRefusal("DocumentVersionPending", "a version is already pending", status=409)
        version_id = self._next_id("ver")
        self._pending[(resource, document_id, stream)] = _Pending(version_id=version_id, size=size, patch=patch)
        return {
            "staged": True,
            "document": self._response(resource, document_id),
            "stream": stream,
            "version_id": version_id,
            "security_context": self.security_context(resource, document_id, version_id),
            "upload": self._signed_upload(self.version_url(resource, version_id), size),
        }

    def commit_version(self, resource: str, document_id: str, stream: str, version_id: str) -> dict[str, Any]:
        """🇺🇸 `POST .../versions/{id}/commit` — promotes the pending version; a replay is idempotent.

        🇧🇷 `POST .../versions/{id}/commit` — promove a versão pendente; reenviar é idempotente.
        """
        if self.fail_next_commits > 0:
            self.fail_next_commits -= 1
            raise _VaultRefusal("ServiceUnavailable", "try again", status=503)
        index = self._index(resource, document_id)
        state = index["streams"][stream]
        if any(v["version_id"] == version_id for v in state["versions"]):
            return {"document": self._response(resource, document_id)}
        pending = self._pending.get((resource, document_id, stream))
        if pending is None or pending.version_id != version_id:
            raise _VaultRefusal("DocumentVersionNotPending", version_id, status=409)
        stored = self._objects.get(self.version_url(resource, version_id))
        if stored is None:
            raise _VaultRefusal("DocumentObjectNotFound", version_id, status=400)
        now = self.now()
        state["versions"].append(
            {"version_id": version_id, "size": len(stored), "created_at": now, "created_by": ACTOR}
        )
        state["latest_version_id"] = version_id
        patch = pending.patch
        if "meta" in patch:
            index["meta"] = {**index.get("meta", {}), **patch["meta"]}
        for key in ("encrypted_index", "is_archived", "is_deleted"):
            if key in patch:
                index[key] = patch[key]
        index["updated_at"] = now
        del self._pending[(resource, document_id, stream)]
        return {"document": self._response(resource, document_id)}

    def get_document(self, resource: str, document_id: str, *, stream: str, version_id: str | None) -> dict[str, Any]:
        """🇺🇸 `GET {base}/{id}` — the index plus a download URL for `version_id` (or the stream's latest).

        🇧🇷 `GET {base}/{id}` — o índice mais uma URL de download de `version_id` (ou da corrente do fluxo).
        """
        index = self._index(resource, document_id)
        state = index["streams"][stream]
        target = version_id or state["latest_version_id"]
        version = next((v for v in state["versions"] if v["version_id"] == target), None)
        if version is None:
            raise _VaultRefusal("DocumentVersionNotFound", str(target))
        return {
            "document": self._response(resource, document_id),
            "stream": stream,
            "version": dict(version),
            "security_context": self.security_context(resource, document_id, version["version_id"]),
            "download": self._signed_download(self.version_url(resource, version["version_id"])),
        }

    def draft_key_id(self, resource: str, stream: str) -> str:
        """🇺🇸 The fixed key id the vault derives a draft's context from. 🇧🇷 O id fixo do contexto de um rascunho."""
        return f"draft:{stream}" if len(_STREAMS[resource]) > 1 else "draft"

    def put_draft(self, resource: str, document_id: str, stream: str, body: dict[str, Any]) -> dict[str, Any]:
        """🇺🇸 `PUT .../draft` — reserves the draft head's signed `PUT` and bumps its `rev`.

        🇧🇷 `PUT .../draft` — reserva o `PUT` assinado da cabeça de rascunho e incrementa o `rev`.
        """
        index = self._index(resource, document_id)
        state = index["streams"][stream]
        current = state.get("draft")
        expected = body.get("draft_rev")
        if expected is not None and current is not None and expected != current["rev"]:
            raise _VaultRefusal("DocumentDraftMismatch", "draft was overwritten", status=409)
        rev = (current["rev"] + 1) if current is not None else 1
        state["draft"] = {"rev": rev, "size": body["content_length"], "updated_at": self.now(), "updated_by": ACTOR}
        return {
            "upload": self._signed_upload(self.draft_url(resource, document_id, stream), body["content_length"]),
            "security_context": self.security_context(resource, document_id, self.draft_key_id(resource, stream)),
            "draft_rev": rev,
        }

    def get_draft(self, resource: str, document_id: str, stream: str) -> dict[str, Any] | None:
        """🇺🇸 `GET .../draft` — `null` when the stream never had one.

        🇧🇷 `GET .../draft` — `null` quando o fluxo nunca teve.
        """
        draft = self._index(resource, document_id)["streams"][stream].get("draft")
        if draft is None:
            return None
        return {
            "download": self._signed_download(self.draft_url(resource, document_id, stream)),
            "security_context": self.security_context(resource, document_id, self.draft_key_id(resource, stream)),
            "draft_rev": draft["rev"],
            "draft_size": draft["size"],
            "updated_at": draft["updated_at"],
        }

    def seed_draft(self, resource: str, document_id: str, sealed: bytes, *, stream: str = "data") -> None:
        """🇺🇸 What the web editor's autosave does: `PUT .../draft` then the object `PUT`, in one step.

        🇧🇷 O que o autosave do editor web faz: `PUT .../draft` e depois o `PUT` do objeto, num passo só.
        """
        reservation = self.put_draft(resource, document_id, stream, {"content_length": len(sealed)})
        self._objects[reservation["upload"]["url"]] = sealed

    # -- nodes (drive files and folders) ---------------------------------------

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


_RouteHandler = Callable[[FakeVault, dict[str, str], dict[str, str], dict[str, Any]], httpx.Response]


def _stream_of(groups: dict[str, str]) -> str:
    """🇺🇸 The stream a version/draft route touches: from the path, or the implicit `data`.

    🇧🇷 O fluxo que uma rota de versão/rascunho toca: do path, ou o `data` implícito.
    """
    return groups.get("stream") or "data"


def _list_documents_route(
    vault: FakeVault, groups: dict[str, str], query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET {base}`. 🇧🇷 `GET {base}`."""
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
    """🇺🇸 `POST {base}`. 🇧🇷 `POST {base}`."""
    return _envelope_success(vault.create_document(groups["resource"], body), status=201)


def _get_document_route(
    vault: FakeVault, groups: dict[str, str], query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET {base}/{document_id}`. 🇧🇷 `GET {base}/{document_id}`."""
    resource = groups["resource"]
    stream = query.get("stream", "data") if len(_STREAMS[resource]) > 1 else "data"
    result = vault.get_document(resource, groups["document_id"], stream=stream, version_id=query.get("version_id"))
    return _envelope_success(result)


def _stage_version_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST .../versions`. 🇧🇷 `POST .../versions`."""
    result = vault.stage_version(groups["resource"], groups["document_id"], _stream_of(groups), body)
    return _envelope_success(result, status=201 if result["staged"] else 200)


def _commit_version_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `POST .../versions/{version_id}/commit`. 🇧🇷 `POST .../versions/{version_id}/commit`."""
    result = vault.commit_version(groups["resource"], groups["document_id"], _stream_of(groups), groups["version_id"])
    return _envelope_success(result)


def _get_draft_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], _body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `GET .../draft`. 🇧🇷 `GET .../draft`."""
    return _envelope_success(vault.get_draft(groups["resource"], groups["document_id"], _stream_of(groups)))


def _put_draft_route(
    vault: FakeVault, groups: dict[str, str], _query: dict[str, str], body: dict[str, Any]
) -> httpx.Response:
    """🇺🇸 `PUT .../draft`. 🇧🇷 `PUT .../draft`."""
    return _envelope_success(vault.put_draft(groups["resource"], groups["document_id"], _stream_of(groups), body))


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


_WS = WORKSPACE_ID
_DOCS = rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients|exams|templates)"
_NODES = rf"^/api/external/v1/workspaces/{_WS}/nodes"
# 🇺🇸 Version and draft routes carry `/streams/{stream}` on patients only — the same table the vault
#    builds its routes from, so `/patients/{id}/versions` has no route here, exactly as in production.
# 🇧🇷 Rotas de versão e rascunho carregam `/streams/{fluxo}` só em pacientes — a mesma tabela de que
#    o cofre monta as rotas, então `/patients/{id}/versions` não tem rota aqui, exatamente como em produção.
_STREAM_BASES = (
    rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients)/(?P<document_id>[^/]+)/streams/(?P<stream>data|file)",
    rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>exams|templates)/(?P<document_id>[^/]+)",
)
# 🇺🇸 Ordered most-specific-first: a literal segment (`complete`, `versions`)
# must be tried before the catch-all `{node_id}`/`{document_id}` pattern it
# would otherwise also match.
# 🇧🇷 Ordenado do mais específico primeiro: um segmento literal (`complete`,
# `versions`) precisa ser tentado antes do padrão coringa `{node_id}`/`{document_id}`
# que também bateria nele.
_ROUTES: list[tuple[re.Pattern[str], str, _RouteHandler]] = [
    (re.compile(rf"{_DOCS}$"), "GET", _list_documents_route),
    (re.compile(rf"{_DOCS}$"), "POST", _create_document_route),
    *(
        route
        for base in _STREAM_BASES
        for route in (
            (re.compile(rf"{base}/versions$"), "POST", _stage_version_route),
            (re.compile(rf"{base}/versions/(?P<version_id>[^/]+)/commit$"), "POST", _commit_version_route),
            (re.compile(rf"{base}/draft$"), "GET", _get_draft_route),
            (re.compile(rf"{base}/draft$"), "PUT", _put_draft_route),
        )
    ),
    (re.compile(rf"{_DOCS}/(?P<document_id>[^/]+)$"), "GET", _get_document_route),
    (re.compile(rf"{_NODES}/uploads$"), "POST", _stage_nodes_route),
    (re.compile(rf"{_NODES}/uploads/complete$"), "POST", _complete_single_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart$"), "POST", _start_multipart_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart/parts$"), "POST", _sign_parts_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart/complete$"), "POST", _complete_multipart_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)/multipart/abort$"), "POST", _abort_multipart_route),
    (re.compile(rf"{_NODES}$"), "GET", _list_nodes_route),
    (re.compile(rf"{_NODES}/(?P<node_id>[^/]+)$"), "GET", _get_node_route),
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
    sleeps: list[float] = field(default_factory=list)

    def keyring_provider(self) -> Keyring:
        """🇺🇸 The callable shape `VersionedDocuments`/`Drive` expect for `keyring_provider`.

        🇧🇷 A forma de callable que `VersionedDocuments`/`Drive` esperam para `keyring_provider`.
        """
        return self.keyring


def _default_group_deks() -> dict[str, bytes]:
    """🇺🇸 Two named security groups with fresh, independent DEKs.

    A plain function, not a fixture: `harness` is the only fixture a test
    file needs to import (the bare-import convention — see the module
    docstring), and it calls this on its own rather than depending on a
    `group_deks` fixture that a test module importing only `harness` would
    never register.

    🇧🇷 Dois security groups nomeados com DEKs novas e independentes.

    Uma função simples, não uma fixture: `harness` é a única fixture que um
    arquivo de teste precisa importar (convenção de import direto — ver a
    docstring do módulo), e ela chama isto por conta própria em vez de
    depender de uma fixture `group_deks` que um módulo de teste importando
    só `harness` nunca registraria.
    """
    return {"sg1": secrets.token_bytes(32), "sg2": secrets.token_bytes(32)}


@pytest.fixture
def harness() -> Harness:
    """🇺🇸 A ready-to-use `Harness`. 🇧🇷 Um `Harness` pronto para uso."""
    return _build_harness(_default_group_deks())


def _build_harness(group_deks: dict[str, bytes]) -> Harness:
    """🇺🇸 Wires a fresh `FakeVault` to a real `VaultTransport` over `httpx.MockTransport`.

    🇧🇷 Conecta um `FakeVault` novo a um `VaultTransport` de verdade sobre `httpx.MockTransport`.
    """
    vault = FakeVault()
    keyring = make_keyring(group_deks)
    settings = Settings(api_token="apikey-test", vault_url=VAULT_URL)  # noqa: S106 — test fixture, not a real secret
    api_client = httpx.Client(transport=httpx.MockTransport(vault.handle_api), base_url=VAULT_URL)
    storage_client = httpx.Client(transport=httpx.MockTransport(vault.handle_storage))
    entropy = EntropyMixer()
    transport = VaultTransport(
        settings,
        _token(),
        session_keys=lambda: keyring.session,
        client=api_client,
        storage_client=storage_client,
        sleep=lambda _seconds: None,
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
    harness: Harness, *, resource: ResourceKind, record_model: type[RecordT], summary_model: type[SummaryT]
) -> VersionedDocuments[RecordT, SummaryT]:
    """🇺🇸 A `VersionedDocuments` wired to `harness`, with a no-op `sleep` so retries cost no wall time.

    🇧🇷 Um `VersionedDocuments` conectado a `harness`, com `sleep` que não faz nada para retentativas não custarem tempo.
    """
    return VersionedDocuments(
        harness.transport,
        harness.keyring_provider,
        harness.entropy,
        workspace_id=WORKSPACE_ID,
        resource=resource,
        record_model=record_model,
        summary_model=summary_model,
        sleep=harness.sleeps.append,
    )
