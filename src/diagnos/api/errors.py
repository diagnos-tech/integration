"""Maps every `diagnos` exception to the API's one error envelope: `{"error": {code, message, trace_id}}`.

A caller of this API reaches `diagnos` only through this facade, so it should never need to know that Python exception
classes exist, only that every non-2xx response has the same three fields to branch on.
`register_exception_handlers` is the single place that mapping lives, so a route never writes its own `try/except`: it
calls the SDK and lets whichever `diagnos` exception comes back propagate to here.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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
from diagnos.api.schemas import ErrorResponse

logger = logging.getLogger("diagnos.api")

_Handler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _documented(description: str) -> dict[str, Any]:
    """Returns one OpenAPI response entry: the uniform envelope, described by `description`."""
    return {"model": ErrorResponse, "description": description}


# The OpenAPI side of `register_exception_handlers` below: the same statuses and the same envelope, kept next to the
# handlers so the documented errors and the real ones cannot drift apart. Without this, FastAPI would document its own
# `{"detail": …}` 422, which this API never sends.
MTLS_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _documented("No client certificate reached this route (`client_certificate_required`)."),
    403: _documented(
        "The client certificate's CN is not in `DIAGNOS_API_ALLOWED_CLIENT_CN` (`client_certificate_cn_not_allowed`)."
    ),
}
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _documented("The vault refused the request as invalid."),
    401: _documented("No client certificate, or the SDK session was rejected or expired (`session_expired`)."),
    402: _documented("The workspace has no credit for this."),
    403: _documented(
        "CN not allowed, permission denied, or no key for the data's security group (`group_key_unavailable`)."
    ),
    404: _documented("Not found; also a node read under a group it does not belong to."),
    409: _documented("A pending or newer version, a replay, or an upload that never reached storage."),
    422: _documented("The body or query failed validation (`invalid_request`)."),
    429: _documented("Rate limited, after the SDK's own backoff gave up."),
    500: _documented("An envelope did not open (`crypto_error`, no detail on purpose)."),
    502: _documented("The vault failed, or answered outside the protocol (`protocol_error`)."),
}


def _body(code: str, message: str, trace_id: str | None) -> dict[str, Any]:
    """Returns the one JSON shape every error response has."""
    return {"error": {"code": code, "message": message, "trace_id": trace_id}}


def _vault_error_handler(status_code: int) -> _Handler:
    """Builds a handler for one `VaultError` subclass, carrying its `code`, `message` and `trace_id` through as-is."""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        """Answers with the status fixed at registration; Starlette dispatches only `VaultError` subclasses here.

        See `docs/PROTOCOL.md §12` for the vault's error taxonomy.
        """
        assert isinstance(exc, VaultError)
        return JSONResponse(status_code=status_code, content=_body(exc.code, exc.message, exc.trace_id))

    return handler


async def _session_expired_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answers 401 for `SessionExpiredError`, a plain `DiagnosError` that carries no `code` or `trace_id`."""
    assert isinstance(exc, SessionExpiredError)
    return JSONResponse(status_code=401, content=_body("session_expired", str(exc), None))


async def _crypto_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answers 500 with no detail: `CryptoError` deliberately conflates "wrong key" and "tampered ciphertext".

    Repeating that conflation here, instead of forwarding whatever message the SDK attached, keeps this endpoint from
    becoming the oracle that the docstring of `diagnos.errors.CryptoError` says a split class would be.
    """
    assert isinstance(exc, CryptoError)
    logger.error("crypto error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=_body("crypto_error", "internal cryptographic error", None))


async def _group_key_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answers 403: this process's enrollment was never handed the key of the group the data belongs to.

    This is a permission gap, not a crypto failure: once an admin approves a new enrollment covering that group, the
    same request succeeds.
    """
    assert isinstance(exc, GroupKeyUnavailable)
    return JSONResponse(status_code=403, content=_body("group_key_unavailable", str(exc), None))


async def _protocol_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answers 502: the vault replied outside the protocol; an upstream fault, not the caller's and not retryable."""
    assert isinstance(exc, ProtocolError)
    logger.error("vault protocol violation handling %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=502, content=_body("protocol_error", str(exc), None))


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Passes through the envelope that `mtls.require_client_certificate` puts in `detail`, or wraps a plain string.

    FastAPI's default `HTTPException` handler wraps whatever `detail` is under `{"detail": ...}`, which would nest the
    `{"error": {code, message, trace_id}}` of `mtls.py` one level too deep. Registering this handler instead keeps
    every non-2xx response in this API, mTLS rejections included, at the same top-level shape.

    It is registered for Starlette's base `HTTPException`, not FastAPI's subclass: the router itself raises the base
    class for an unknown route (404) or a wrong method (405), and a handler for the subclass would never see those.
    """
    assert isinstance(exc, StarletteHTTPException)
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
    body = _body("http_error", str(exc.detail), None)
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Folds FastAPI's `RequestValidationError` for a malformed body or query into the same envelope."""
    assert isinstance(exc, RequestValidationError)
    detail = "; ".join(f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors())
    return JSONResponse(status_code=422, content=_body("invalid_request", detail or "invalid request", None))


async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Falls back for any `DiagnosError` this module did not name explicitly (`ConfigError`, enrollment errors).

    This process's `Diagnos` is already unlocked by the time any route runs (the lifespan in `app.py`), so these are
    not expected in practice. The handler exists so an unforeseen one still returns the uniform envelope instead of
    Starlette's raw-traceback 500.
    """
    logger.exception("unhandled diagnos error")
    return JSONResponse(status_code=500, content=_body("internal_error", "an unexpected error occurred", None))


def register_exception_handlers(app: FastAPI) -> None:
    """Wires every mapping above into `app`, most specific first (Starlette walks the MRO to the nearest match)."""
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
