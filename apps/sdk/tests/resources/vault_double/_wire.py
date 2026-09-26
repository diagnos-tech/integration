"""🇺🇸 The tiny plumbing every `vault_double` submodule shares.

Identity constants, the two envelope shapes `handle_api` wraps every response in, and the
control-flow signal a route handler raises to produce an error envelope. Kept as its own module —
imported with a leading dot by every sibling, never re-exported through `__init__.py` — so
`_documents.py` and `_nodes.py` can reach it without going through the package's own `__init__.py`
first, which would otherwise be a straight import cycle: `_core.py` needs
`DOCUMENT_ROUTES`/`NODE_ROUTES` from those two modules to build its routing table.

🇧🇷 A pequena base que todo submódulo de `vault_double` compartilha.

Constantes de identidade, as duas formas de envelope em que `handle_api` embrulha toda resposta, e o
sinal de controle de fluxo que um handler de rota lança para produzir um envelope de erro. Mantido
como módulo próprio — importado com ponto por todo irmão, nunca reexportado pelo `__init__.py` —
para `_documents.py` e `_nodes.py` o alcançarem sem passar primeiro pelo próprio `__init__.py` do
pacote, o que seria um ciclo de import: `_core.py` precisa de `DOCUMENT_ROUTES`/`NODE_ROUTES` desses
dois módulos para montar sua tabela de rotas.
"""

from __future__ import annotations

import httpx

WORKSPACE_ID = "ws_1"
VAULT_URL = "https://vault.example.test"
ACTOR = "svc_test"


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
