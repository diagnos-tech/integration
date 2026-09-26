"""🇺🇸 The documents half of the double: `patients`/`exams`/`templates` indexes, versions and drafts.

Follows `routes/factories/versionedDocuments.ts` and `services/documents/store.ts` rule for rule:
stream-aware paths, the singular `security_group_id`, required `encrypted_index`, a signed `PUT`
locked to the declared size, one pending slot per stream, patch-only reservations,
`expected_latest_version_id`, and the draft head.

🇧🇷 A metade de documentos do duplo: índices de `patients`/`exams`/`templates`, versões e rascunhos.

Segue `routes/factories/versionedDocuments.ts` e `services/documents/store.ts` regra por regra: paths
cientes de fluxo, `security_group_id` no singular, `encrypted_index` obrigatório, `PUT` assinado
travado no tamanho declarado, um slot pendente por fluxo, reservas só de patch,
`expected_latest_version_id` e a cabeça de rascunho.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from ._wire import ACTOR, WORKSPACE_ID, _envelope_success, _VaultRefusal

if TYPE_CHECKING:
    from ._core import FakeVault, _RouteHandler

_STREAMS: dict[str, tuple[str, ...]] = {"patients": ("data", "file"), "exams": ("data",), "templates": ("data",)}
_REQUIRES_ENCRYPTED_INDEX = frozenset({"patients", "templates"})
_CREATE_FIELDS = frozenset(
    {"security_group_id", "encrypted_keys", "content_length", "stream", "meta", "encrypted_index"}
)
_STAGE_FIELDS = frozenset(
    {"content_length", "meta", "is_archived", "is_deleted", "encrypted_index", "expected_latest_version_id"}
)


@dataclass
class _Pending:
    """🇺🇸 A reserved version of one stream, not yet committed, plus the patch that rides with it.

    🇧🇷 Uma versão reservada de um fluxo, ainda não confirmada, mais o patch que viaja com ela.
    """

    version_id: str
    size: int
    patch: dict[str, Any] = field(default_factory=dict)


class _DocumentsMixin:
    """🇺🇸 `FakeVault`'s document half: indexes, versions, and the draft head, per stream.

    🇧🇷 A metade de documentos do `FakeVault`: índices, versões, e a cabeça de rascunho, por fluxo.
    """

    def version_url(self, resource: str, version_id: str) -> str:
        """🇺🇸 Where a version's object lives (flat by `version_id`, as in R2). 🇧🇷 Onde mora o objeto de uma versão."""
        return self._object_url(f"workspaces/{WORKSPACE_ID}/{resource}/{version_id}")

    def draft_url(self, resource: str, document_id: str, stream: str) -> str:
        """🇺🇸 Where a stream's draft head lives. 🇧🇷 Onde mora a cabeça de rascunho de um fluxo."""
        suffix = f"/{stream}" if len(_STREAMS[resource]) > 1 else ""
        return self._object_url(f"workspaces/{WORKSPACE_ID}/{resource}/{document_id}/draft{suffix}")

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


_WS = WORKSPACE_ID
_DOCS = rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients|exams|templates)"
# 🇺🇸 Version and draft routes carry `/streams/{stream}` on patients only — the same table the vault
#    builds its routes from, so `/patients/{id}/versions` has no route here, exactly as in production.
# 🇧🇷 Rotas de versão e rascunho carregam `/streams/{fluxo}` só em pacientes — a mesma tabela de que
#    o cofre monta as rotas, então `/patients/{id}/versions` não tem rota aqui, exatamente como em produção.
_STREAM_BASES = (
    rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>patients)/(?P<document_id>[^/]+)/streams/(?P<stream>data|file)",
    rf"^/api/external/v1/workspaces/{_WS}/(?P<resource>exams|templates)/(?P<document_id>[^/]+)",
)

DOCUMENT_ROUTES: list[tuple[re.Pattern[str], str, _RouteHandler]] = [
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
]
