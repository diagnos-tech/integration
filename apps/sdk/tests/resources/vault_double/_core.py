"""🇺🇸 `FakeVault`: the router tying the documents, nodes and storage mixins to one shared clock.

Also holds `_next_id`'s counter, the API request log, and `security_context` — the one payload
shape both halves hand out. `FakeVault` is deliberately not a mock of `VaultTransport`'s methods — it is a real
`httpx.MockTransport` handler, plain Python dicts standing in for Firestore and R2, so a bug in how
`resources/` builds a request (a wrong path, a missing field, a `content-length` that does not match
the body it sends) shows up as a real HTTP-shaped failure, the same way it would against the vault.

🇧🇷 `FakeVault`: o roteador que amarra os mixins de documentos, nós e armazenamento a um relógio,
contador e log de requisições compartilhados, mais `security_context` — a forma de payload que as
duas metades entregam.

`FakeVault` de propósito não é um mock dos métodos de `VaultTransport` — é um handler de
`httpx.MockTransport` de verdade, dicts Python puros no lugar do Firestore e do R2, para um bug em como
`resources/` monta uma requisição (um path errado, um campo faltando, um `content-length` que não bate
com o corpo que manda) aparecer como uma falha HTTP de verdade, do mesmo jeito que apareceria contra o
cofre.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ._documents import DOCUMENT_ROUTES, _DocumentsMixin, _Pending
from ._nodes import NODE_ROUTES, _NodesMixin
from ._storage import _StorageMixin
from ._wire import WORKSPACE_ID, _envelope_error, _time_response, _VaultRefusal

_RouteHandler = Callable[["FakeVault", dict[str, str], dict[str, str], dict[str, Any]], httpx.Response]

# 🇺🇸 Ordered document routes first, then node/drive routes — the same relative order the original,
#    unsplit double used; within each group a literal segment is tried before a catch-all id.
# 🇧🇷 Rotas de documento primeiro, depois rotas de nó/drive — a mesma ordem relativa do duplo original,
#    não dividido; dentro de cada grupo um segmento literal é tentado antes de um id coringa.
_ROUTES: list[tuple[re.Pattern[str], str, _RouteHandler]] = [*DOCUMENT_ROUTES, *NODE_ROUTES]


class FakeVault(_DocumentsMixin, _NodesMixin, _StorageMixin):
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
        self.single_threshold = 1_000_000
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

    @staticmethod
    def security_context(resource: str, document_id: str, key_id: str) -> dict[str, str]:
        """🇺🇸 The deterministic `security_context` of one object — a test can derive the same content key.

        🇧🇷 O `security_context` determinístico de um objeto — um teste consegue derivar a mesma chave de conteúdo.
        """
        raw = f"ctx|{WORKSPACE_ID}|{resource}|{document_id}|{key_id}".encode()
        return {"value": base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"), "kid": "ctx_k1"}

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
