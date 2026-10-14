"""Mutual TLS: the API's one and only authentication mechanism.

A password or a bearer token can leak: copied into a chat, committed by accident, replayed from a stolen log. A client
certificate signed by a CA this deployment chose to trust cannot be reproduced from a leaked secret alone, because the
caller has to hold the private key the CA signed, and that key never travels over the wire. That is why this API never
accepts `Authorization` headers, API keys, or `X-Forwarded-*` identity from a reverse proxy. A proxy header is just a
string that an attacker who reached the proxy can set to anything, while the TLS client certificate is the one thing on
the request that uvicorn itself verified cryptographically before a single byte of application code ran.

`ssl_config_for_uvicorn` configures that verification (`ssl.CERT_REQUIRED`); `ClientCertH11Protocol` carries the
verified certificate from uvicorn's connection object into the ASGI request every route depends on;
`require_client_certificate` turns it into the `ClientIdentity` a route can trust.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from uvicorn.protocols.http.h11_impl import H11Protocol

from diagnos.api.settings import ApiSettings


@dataclass(frozen=True)
class ClientIdentity:
    """Who is calling: the verified subject of the client certificate uvicorn accepted for this connection."""

    common_name: str
    serial: str


def ssl_config_for_uvicorn(settings: ApiSettings) -> dict[str, Any]:
    """Returns the `ssl_*` keyword arguments with which `uvicorn.run` and `uvicorn.Config` require a client certificate.

    `ssl_cert_reqs=ssl.CERT_REQUIRED` makes the handshake itself refuse a connection that never presents a certificate
    signed by `ssl_ca_certs`. A request without one never becomes an HTTP request at all, so
    `require_client_certificate` only ever has to interpret a certificate that already passed chain verification,
    never decide whether one was required.
    """
    return {
        "ssl_certfile": settings.tls_cert_file,
        "ssl_keyfile": settings.tls_key_file,
        "ssl_ca_certs": settings.mtls_ca_file,
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }


class ClientCertH11Protocol(H11Protocol):
    """uvicorn's HTTP/1.1 protocol, patched to carry the raw connection into the ASGI scope.

    Plain uvicorn never puts the `asyncio.Transport` of a connection into the ASGI `scope` it hands the application,
    and there is no ASGI-standard way to reach `ssl_object.getpeercert()` from inside a route otherwise. Every place
    in `H11Protocol` that starts a request assigns a brand new dict to `self.scope`. Overriding `scope` as a property,
    rather than duplicating that request-parsing logic, lets this class track upstream uvicorn without modification
    for as long as that one assignment keeps existing.

    Pass this class as `uvicorn.run(..., http=ClientCertH11Protocol)`. It is the only way
    `require_client_certificate` ever finds a certificate in production; tests use `create_app`'s
    `trusted_test_identity` instead, since `TestClient` never runs a real TLS handshake.
    """

    # mypy flags this whole property/setter pair against the third-party base class's plain instance attribute
    # (`self.scope: HTTPScope = None` in `H11Protocol.__init__`). Narrowing that attribute into a property is exactly
    # the point of this class, and the runtime behavior (still a settable `self.scope`) is what `H11Protocol` expects.
    @property  # type: ignore[override]
    def scope(self) -> dict[str, Any] | None:
        """The ASGI scope for the request currently being parsed, or `None` between requests."""
        return self.__dict__.get("_client_cert_scope")

    @scope.setter
    def scope(self, value: dict[str, Any] | None) -> None:
        """Stamps `transport` onto every new scope so it survives into the ASGI request."""
        if value is not None:
            value["transport"] = self.transport
        self.__dict__["_client_cert_scope"] = value


def _common_name(cert: dict[str, Any]) -> str | None:
    """Returns the certificate's `commonName` from the nested RDN tuples of `ssl.SSLObject.getpeercert()`."""
    for rdn in cert.get("subject", ()):
        for key, value in rdn:
            if key == "commonName":
                return str(value)
    return None


def _identity_from_request(request: Request) -> ClientIdentity | None:
    """Reads the peer certificate that `ClientCertH11Protocol` attached to this connection, if any."""
    transport = request.scope.get("transport")
    if transport is None:
        return None
    ssl_object = transport.get_extra_info("ssl_object")
    if ssl_object is None:
        return None
    cert = ssl_object.getpeercert()
    if not cert:
        return None
    common_name = _common_name(cert)
    if common_name is None:
        return None
    return ClientIdentity(common_name=common_name, serial=str(cert.get("serialNumber", "")))


async def require_client_certificate(request: Request) -> ClientIdentity:
    """FastAPI dependency that yields the caller's verified identity, or fails before any route body runs.

    `request.app.state.trusted_test_identity` is the one deliberate escape hatch. Only `create_app` sets it, and only
    in tests (`conftest.py`), never in production, because `TestClient` talks ASGI in-process and never negotiates real
    TLS. Every other caller has to have come through `ClientCertH11Protocol` over an actual mTLS connection.

    Args:
        request: The incoming request; its app state carries the settings and the optional test identity.

    Returns:
        The caller's `ClientIdentity`.

    Raises:
        HTTPException: 401 (`client_certificate_required`) when no certificate identifies the caller, or 403
            (`client_certificate_cn_not_allowed`) when `DIAGNOS_API_ALLOWED_CLIENT_CN` is set and excludes its CN.
    """
    trusted_test_identity: ClientIdentity | None = getattr(request.app.state, "trusted_test_identity", None)
    identity = trusted_test_identity if trusted_test_identity is not None else _identity_from_request(request)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "client_certificate_required",
                    "message": "no client certificate was presented for this connection.",
                    "trace_id": None,
                }
            },
        )
    settings: ApiSettings = request.app.state.settings
    if settings.allowed_client_cns and identity.common_name not in settings.allowed_client_cns:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "client_certificate_cn_not_allowed",
                    "message": f"client certificate CN {identity.common_name!r} is not in the allowed list.",
                    "trace_id": None,
                }
            },
        )
    return identity
