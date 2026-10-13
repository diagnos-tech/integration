"""🇺🇸 Unwraps the vault's response envelope (`docs/PROTOCOL.md §0`).

Every vault response, success or failure, is the same shape. Callers decide
by `code`, never by `message` (`docs/PROTOCOL.md §0`) — `message` is meant
for a human, `code` is the contract — so this module's whole job is turning
`success: false` plus an HTTP status into the one SDK exception the caller
should catch.

🇧🇷 Desembrulha o envelope de resposta do cofre (`docs/PROTOCOL.md §0`).

Toda resposta do cofre, sucesso ou falha, tem a mesma forma. Quem chama
decide por `code`, nunca por `message` (`docs/PROTOCOL.md §0`) — `message` é
para um humano, `code` é o contrato — então o trabalho deste módulo é virar
`success: false` mais um status HTTP na única exceção do SDK que quem chamou
deve capturar.
"""

from __future__ import annotations

from typing import Any

import httpx

from diagnos.errors import (
    AuthenticationError,
    ConflictError,
    DiagnosPermissionError,
    NotFoundError,
    QuotaError,
    RateLimitError,
    ValidationError,
    VaultError,
)

# 🇺🇸 `docs/PROTOCOL.md §12`. Anything not listed here (5xx included) is a
# plain `VaultError` — the caller still gets `code`/`status`/`trace_id`, it
# just has no more specific recovery than "ask a human" or "retry later."
# 🇧🇷 `docs/PROTOCOL.md §12`. O que não está listado aqui (5xx incluso) vira
# `VaultError` puro — quem chama ainda recebe `code`/`status`/`trace_id`, só
# não tem recuperação mais específica que "pedir ajuda" ou "tentar depois".
_STATUS_EXCEPTIONS: dict[int, type[VaultError]] = {
    400: ValidationError,
    401: AuthenticationError,
    402: QuotaError,
    403: DiagnosPermissionError,
    404: NotFoundError,
    409: ConflictError,
    413: ValidationError,
    429: RateLimitError,
}


def unwrap_result(response: httpx.Response) -> Any:
    """🇺🇸 Return `result` on success; raise the mapped `VaultError` on failure.

    A response that is not even JSON (a proxy's HTML error page, a truncated
    body) cannot carry a `code` at all, so it becomes `VaultError` with the
    synthetic code `InvalidResponse` rather than an unrelated `JSONDecodeError`
    leaking out of a transport module.

    🇧🇷 Retorna `result` no sucesso; lança o `VaultError` mapeado na falha.

    Uma resposta que nem é JSON (página de erro HTML de um proxy, corpo
    truncado) não carrega `code` nenhum, então vira `VaultError` com o código
    sintético `InvalidResponse` em vez de deixar vazar um `JSONDecodeError`
    sem relação nenhuma com o transporte.
    """
    request_id = response.headers.get("X-Request-Id")
    try:
        data = response.json()
    except ValueError as exc:
        raise VaultError(
            code="InvalidResponse",
            message=("🇺🇸 The vault's response was not valid JSON. 🇧🇷 A resposta do cofre não era JSON válido."),
            status=response.status_code,
            request_id=request_id,
        ) from exc

    if isinstance(data, dict) and data.get("success") is True:
        return data.get("result")

    errors = data.get("errors") if isinstance(data, dict) else None
    first = errors[0] if isinstance(errors, list) and errors else {}
    code = first.get("code", "Unknown") if isinstance(first, dict) else "Unknown"
    message = first.get("message", "") if isinstance(first, dict) else ""
    trace_id = first.get("trace_id") if isinstance(first, dict) else None

    exception_class = _STATUS_EXCEPTIONS.get(response.status_code, VaultError)
    raise exception_class(
        code=code,
        message=message,
        status=response.status_code,
        trace_id=trace_id,
        request_id=request_id,
    )
