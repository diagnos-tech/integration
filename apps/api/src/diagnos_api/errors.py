"""🇺🇸 Maps every `diagnos` exception to the API's one error envelope: `{"error": {code, message, trace_id}}`.

A caller of this API only ever imports `diagnos` transitively through this
facade — it should never have to know Python exception classes exist at
all, only that every non-2xx response has the same three fields to branch
on. `register_exception_handlers` is the single place that mapping lives,
so a route never writes its own `try/except`: it just calls the SDK and
lets whichever `diagnos` exception comes back propagate to here.

🇧🇷 Mapeia toda exceção do `diagnos` para o único envelope de erro da API:
`{"error": {code, message, trace_id}}`.

Quem chama esta API só importa `diagnos` de forma transitiva, através desta
fachada — não deveria nem saber que classes de exceção Python existem, só
que toda resposta não-2xx tem os mesmos três campos para decidir o que
fazer. `register_exception_handlers` é o único lugar onde esse mapeamento
mora, então uma rota nunca escreve o próprio `try/except`: só chama o SDK e
deixa qualquer exceção do `diagnos` que voltar se propagar até aqui.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from diagnos import (
    AuthenticationError,
    ConflictError,
    CryptoError,
    DiagnosError,
    DiagnosPermissionError,
    GroupKeyUnavailable,
    NotFoundError,
    ProtocolError,
    QuotaError,
    RateLimitError,
    SessionExpiredError,
    ValidationError,
    VaultError,
)
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from diagnos_api.schemas import ErrorResponse

logger = logging.getLogger("diagnos_api")

_Handler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _documented(description: str) -> dict[str, Any]:
    """🇺🇸 One OpenAPI response entry: the uniform envelope, with a bilingual description.

    🇧🇷 Uma entrada de resposta do OpenAPI: o envelope uniforme, com uma descrição bilíngue.
    """
    return {"model": ErrorResponse, "description": description}


# 🇺🇸 The OpenAPI side of `register_exception_handlers` below — the same statuses and the same envelope, kept
#    next to the handlers so the documented errors and the real ones cannot drift apart. Without this, FastAPI
#    would document its own `{"detail": …}` 422, which this API never sends.
# 🇧🇷 O lado OpenAPI de `register_exception_handlers` abaixo — os mesmos status e o mesmo envelope, ao lado
#    dos handlers para os erros documentados e os reais não se separarem. Sem isto, o FastAPI documentaria o
#    próprio 422 `{"detail": …}`, que esta API nunca manda.
MTLS_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _documented(
        "🇺🇸 No client certificate reached this route (`client_certificate_required`). "
        "🇧🇷 Nenhum certificado de cliente chegou a esta rota (`client_certificate_required`)."
    ),
    403: _documented(
        "🇺🇸 The client certificate's CN is not in `DIAGNOS_API_ALLOWED_CLIENT_CN` "
        "(`client_certificate_cn_not_allowed`). "
        "🇧🇷 O CN do certificado de cliente não está em `DIAGNOS_API_ALLOWED_CLIENT_CN` "
        "(`client_certificate_cn_not_allowed`)."
    ),
}
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _documented("🇺🇸 The vault refused the request as invalid. 🇧🇷 O cofre recusou a requisição como inválida."),
    401: _documented(
        "🇺🇸 No client certificate, or the SDK session was rejected or expired (`session_expired`). "
        "🇧🇷 Sem certificado de cliente, ou a sessão do SDK foi recusada ou expirou (`session_expired`)."
    ),
    402: _documented("🇺🇸 The workspace has no credit for this. 🇧🇷 O workspace não tem crédito para isto."),
    403: _documented(
        "🇺🇸 CN not allowed, permission denied, or no key for the data's security group "
        "(`group_key_unavailable`). "
        "🇧🇷 CN não permitido, permissão negada, ou sem chave para o security group do dado "
        "(`group_key_unavailable`)."
    ),
    404: _documented(
        "🇺🇸 Not found — also a node read under a group it does not belong to. "
        "🇧🇷 Não encontrado — também um nó lido sob um grupo ao qual não pertence."
    ),
    409: _documented(
        "🇺🇸 A pending or newer version, a replay, or an upload that never reached storage. "
        "🇧🇷 Uma versão pendente ou mais nova, um replay, ou um upload que não chegou ao armazenamento."
    ),
    422: _documented(
        "🇺🇸 The body or query failed validation (`invalid_request`). "
        "🇧🇷 O corpo ou a query falhou na validação (`invalid_request`)."
    ),
    429: _documented(
        "🇺🇸 Rate limited, after the SDK's own backoff gave up. 🇧🇷 Limite de taxa, depois de o backoff do SDK desistir."
    ),
    500: _documented(
        "🇺🇸 An envelope did not open (`crypto_error`, no detail on purpose). "
        "🇧🇷 Um envelope não abriu (`crypto_error`, sem detalhe de propósito)."
    ),
    502: _documented(
        "🇺🇸 The vault failed, or answered outside the protocol (`protocol_error`). "
        "🇧🇷 O cofre falhou, ou respondeu fora do protocolo (`protocol_error`)."
    ),
}


def _body(code: str, message: str, trace_id: str | None) -> dict[str, Any]:
    """🇺🇸 The one JSON shape every error response has. 🇧🇷 A única forma de JSON que toda resposta de erro tem."""
    return {"error": {"code": code, "message": message, "trace_id": trace_id}}


def _vault_error_handler(status_code: int) -> _Handler:
    """🇺🇸 Builds a handler for one `VaultError` subclass, carrying its `code`/`message`/`trace_id` through as-is.

    🇧🇷 Constrói um handler para uma subclasse de `VaultError`, carregando `code`/`message`/`trace_id` como estão.
    """

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        """🇺🇸 Starlette only ever dispatches a registered `VaultError` subclass here (`docs/PROTOCOL.md §12`).

        🇧🇷 O Starlette só despacha aqui uma subclasse registrada de `VaultError` (`docs/PROTOCOL.md §12`).
        """
        assert isinstance(exc, VaultError)
        return JSONResponse(status_code=status_code, content=_body(exc.code, exc.message, exc.trace_id))

    return handler


async def _session_expired_handler(request: Request, exc: Exception) -> JSONResponse:
    """🇺🇸 `SessionExpiredError` is a plain `DiagnosError`, not a `VaultError` — it carries no `code`/`trace_id`.

    🇧🇷 `SessionExpiredError` é um `DiagnosError` puro, não um `VaultError` — não carrega `code`/`trace_id`.
    """
    assert isinstance(exc, SessionExpiredError)
    return JSONResponse(status_code=401, content=_body("session_expired", str(exc), None))


async def _crypto_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """🇺🇸 500, with no detail: `CryptoError` deliberately conflates "wrong key" and "tampered ciphertext".

    Repeating that conflation here — instead of forwarding whatever message
    the SDK attached — is what keeps this endpoint from becoming the oracle
    `diagnos.errors.CryptoError`'s own docstring says a split class would be.

    🇧🇷 500, sem detalhe: `CryptoError` deliberadamente confunde "chave
    errada" com "ciphertext adulterado".

    Repetir essa confusão aqui — em vez de encaminhar a mensagem que o SDK
    anexou — é o que impede este endpoint de virar o oráculo que a própria
    docstring de `diagnos.errors.CryptoError` diz que uma classe separada
    seria.
    """
    assert isinstance(exc, CryptoError)
    logger.error("crypto error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=_body("crypto_error", "internal cryptographic error", None))


async def _group_key_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """🇺🇸 403: this process's enrollment was never handed the key of the group the data belongs to.

    A permission gap, not a crypto failure: an admin approves a new
    enrollment covering that group, and the same request then succeeds.

    🇧🇷 403: o enrollment deste processo nunca recebeu a chave do grupo a que o dado pertence.

    Uma lacuna de permissão, não uma falha de cripto: um admin aprova um
    enrollment novo cobrindo esse grupo, e a mesma requisição passa.
    """
    assert isinstance(exc, GroupKeyUnavailable)
    return JSONResponse(status_code=403, content=_body("group_key_unavailable", str(exc), None))


async def _protocol_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """🇺🇸 502: the vault answered outside the protocol — an upstream fault, not this caller's and not retryable.

    🇧🇷 502: o cofre respondeu fora do protocolo — falha de quem está acima, não de quem chama, e sem retentativa.
    """
    assert isinstance(exc, ProtocolError)
    logger.error("vault protocol violation handling %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=502, content=_body("protocol_error", str(exc), None))


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """🇺🇸 `mtls.require_client_certificate`'s 401/403 already carry the uniform envelope as `detail` — use it as-is.

    FastAPI's own default `HTTPException` handler wraps whatever `detail` is
    under `{"detail": ...}`, which would nest `mtls.py`'s
    `{"error": {code, message, trace_id}}` one level too deep. Registering
    this here — instead of leaving the default in place — is what keeps
    every non-2xx response in this API, mTLS rejections included, at the
    same top-level shape.

    🇧🇷 O 401/403 de `mtls.require_client_certificate` já carrega o envelope
    uniforme como `detail` — usa-o como está.

    O handler padrão do `HTTPException` do próprio FastAPI embrulha
    qualquer `detail` sob `{"detail": ...}`, o que aninharia o
    `{"error": {code, message, trace_id}}` de `mtls.py` um nível fundo
    demais. Registrar isto aqui — em vez de deixar o padrão — é o que
    mantém toda resposta não-2xx desta API, rejeições de mTLS inclusas, na
    mesma forma de topo.

    🇺🇸 Registered for Starlette's base `HTTPException`, not FastAPI's
    subclass: the router itself raises the base class for an unknown route
    (404) or a wrong method (405), and a handler for the subclass would
    never see those.
    🇧🇷 Registrado para a `HTTPException` base do Starlette, não para a
    subclasse do FastAPI: o próprio roteador lança a classe base para rota
    inexistente (404) ou método errado (405), e um handler da subclasse
    nunca veria esses casos.
    """
    assert isinstance(exc, StarletteHTTPException)
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
    body = _body("http_error", str(exc.detail), None)
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """🇺🇸 A malformed request body/query — FastAPI's own `RequestValidationError`, folded into the same envelope.

    🇧🇷 Um corpo/query de requisição malformado — o `RequestValidationError`
    do próprio FastAPI, dobrado no mesmo envelope.
    """
    assert isinstance(exc, RequestValidationError)
    detail = "; ".join(f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors())
    return JSONResponse(status_code=422, content=_body("invalid_request", detail or "invalid request", None))


async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """🇺🇸 A fallback for any `DiagnosError` this module did not name explicitly (`ConfigError`, enrollment errors).

    This process's `Diagnos` is already unlocked by the time any route runs
    (`app.py`'s lifespan), so these are not expected in practice — this
    exists so an unforeseen one still returns the uniform envelope instead
    of Starlette's raw-traceback 500.

    🇧🇷 Um fallback para todo `DiagnosError` que este módulo não nomeou
    explicitamente (`ConfigError`, erros de enrollment).

    O `Diagnos` deste processo já está desbloqueado quando qualquer rota
    roda (o lifespan de `app.py`), então isso não é esperado na prática —
    isto existe para um caso imprevisto ainda devolver o envelope uniforme
    em vez do 500 com traceback cru do Starlette.
    """
    logger.exception("unhandled diagnos error")
    return JSONResponse(status_code=500, content=_body("internal_error", "an unexpected error occurred", None))


def register_exception_handlers(app: FastAPI) -> None:
    """🇺🇸 Wires every mapping above into `app`, most specific first (Starlette walks the MRO to the nearest match).

    🇧🇷 Conecta todo mapeamento acima em `app`, do mais específico primeiro
    (o Starlette percorre o MRO até o mais próximo).
    """
    app.add_exception_handler(ValidationError, _vault_error_handler(400))
    app.add_exception_handler(AuthenticationError, _vault_error_handler(401))
    app.add_exception_handler(SessionExpiredError, _session_expired_handler)
    app.add_exception_handler(DiagnosPermissionError, _vault_error_handler(403))
    app.add_exception_handler(NotFoundError, _vault_error_handler(404))
    app.add_exception_handler(ConflictError, _vault_error_handler(409))
    app.add_exception_handler(QuotaError, _vault_error_handler(402))
    app.add_exception_handler(RateLimitError, _vault_error_handler(429))
    app.add_exception_handler(VaultError, _vault_error_handler(502))
    app.add_exception_handler(CryptoError, _crypto_error_handler)
    app.add_exception_handler(ProtocolError, _protocol_error_handler)
    app.add_exception_handler(GroupKeyUnavailable, _group_key_unavailable_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(DiagnosError, _unexpected_error_handler)
