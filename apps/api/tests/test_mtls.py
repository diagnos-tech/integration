"""mTLS is the only authentication: no certificate is a 401, a disallowed CN is a 403, and config demands the PEMs.

That includes `/openapi.json` and `/docs` (`routers/docs.py`), which FastAPI would otherwise serve ungated.
"""

from __future__ import annotations

import dataclasses
import ssl
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from diagnos.api.mtls import ClientCertH11Protocol, _identity_from_request, ssl_config_for_uvicorn
from diagnos.api.settings import ApiConfigError, ApiSettings

from conftest import TRUSTED_IDENTITY, FakeDiagnos, build_app


def test_missing_certificate_is_rejected_with_401(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """No `trusted_test_identity` and no real TLS handshake (`TestClient`) means no identity at all."""
    app = build_app(fake_vault, api_settings, trusted_test_identity=None)

    with TestClient(app) as client:
        response = client.get("/v1/session")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "client_certificate_required"


def test_disallowed_cn_is_rejected_with_403(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """`TRUSTED_IDENTITY.common_name` ("ci-client") is not in `allowed_client_cns`, so the allowlist wins."""
    restricted_settings = dataclasses.replace(api_settings, allowed_client_cns=frozenset({"other"}))
    app = build_app(fake_vault, restricted_settings)

    with TestClient(app) as client:
        response = client.get("/v1/session")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "client_certificate_cn_not_allowed"


def test_allowed_cn_passes_through(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """An empty allowlist (the default) or a matching one both let `TRUSTED_IDENTITY` through."""
    allowed = frozenset({TRUSTED_IDENTITY.common_name})
    permissive_settings = dataclasses.replace(api_settings, allowed_client_cns=allowed)
    app = build_app(fake_vault, permissive_settings)

    with TestClient(app) as client:
        response = client.get("/v1/session")

    assert response.status_code == 200
    assert response.json()["client"]["common_name"] == TRUSTED_IDENTITY.common_name


def test_ssl_config_requires_client_certificates(api_settings: ApiSettings) -> None:
    """`ssl_cert_reqs=CERT_REQUIRED` is what makes the TLS handshake itself refuse an anonymous client."""
    config = ssl_config_for_uvicorn(api_settings)

    assert config["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert config["ssl_certfile"] == api_settings.tls_cert_file
    assert config["ssl_keyfile"] == api_settings.tls_key_file
    assert config["ssl_ca_certs"] == api_settings.mtls_ca_file


def test_settings_from_env_requires_the_ca_file() -> None:
    """Without `DIAGNOS_API_MTLS_CA_FILE` (and the cert/key), the process has nothing safe to start with."""
    with pytest.raises(ApiConfigError, match="DIAGNOS_API_MTLS_CA_FILE"):
        ApiSettings.from_env({})


def _request_with_transport(transport: Any) -> SimpleNamespace:
    """Builds a request stand-in; `_identity_from_request` only reads `request.scope.get("transport")`."""
    return SimpleNamespace(scope={"transport": transport})


class _FakeTransport:
    """Stands in for `asyncio.Transport.get_extra_info("ssl_object")`, the one call `_identity_from_request` makes."""

    def __init__(self, ssl_object: Any) -> None:
        self._ssl_object = ssl_object

    def get_extra_info(self, name: str) -> Any:
        """The ASGI transport's `extra_info`; only `"ssl_object"` is ever asked for."""
        assert name == "ssl_object"
        return self._ssl_object


class _FakeSslObject:
    """Stands in for `ssl.SSLObject` with only `getpeercert()`, the one method `_identity_from_request` calls."""

    def __init__(self, cert: dict[str, Any] | None) -> None:
        self._cert = cert

    def getpeercert(self) -> dict[str, Any] | None:
        """The fixed certificate dict this fake was built with."""
        return self._cert


def test_identity_from_request_is_none_without_a_transport_in_scope() -> None:
    """A plain ASGI request with no `transport` key (the normal shape `TestClient` produces) yields no identity."""
    request = SimpleNamespace(scope={})

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_is_none_without_an_ssl_object() -> None:
    """A plain-TCP transport (`get_extra_info("ssl_object")` returns `None`) is not an mTLS connection."""
    request = _request_with_transport(_FakeTransport(ssl_object=None))

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_is_none_for_an_empty_peer_certificate() -> None:
    """`getpeercert()` returning `{}` (TLS negotiated, but no certificate to inspect) is also "no identity"."""
    request = _request_with_transport(_FakeTransport(_FakeSslObject({})))

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_is_none_without_a_common_name() -> None:
    """A certificate whose `subject` carries no `commonName` RDN cannot become a `ClientIdentity`."""
    cert = {"subject": ((("organizationName", "Example Corp"),),), "serialNumber": "01"}
    request = _request_with_transport(_FakeTransport(_FakeSslObject(cert)))

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_reads_common_name_and_serial() -> None:
    """A well-formed peer certificate becomes a `ClientIdentity` carrying its `commonName`/`serialNumber`."""
    cert = {
        "subject": ((("organizationName", "Example Corp"),), (("commonName", "ci-client"),)),
        "serialNumber": "DEADBEEF",
    }
    request = _request_with_transport(_FakeTransport(_FakeSslObject(cert)))

    identity = _identity_from_request(request)  # type: ignore[arg-type]

    assert identity is not None
    assert identity.common_name == "ci-client"
    assert identity.serial == "DEADBEEF"


def test_client_cert_h11_protocol_scope_defaults_to_none() -> None:
    """Before any request is parsed, the patched `scope` property reads back `None`."""
    protocol = object.__new__(ClientCertH11Protocol)

    assert protocol.scope is None


def test_client_cert_h11_protocol_scope_setter_stamps_the_transport() -> None:
    """Assigning a new scope dict stamps this connection's `transport` into it, so it survives into the request."""
    protocol = object.__new__(ClientCertH11Protocol)
    sentinel_transport = object()
    protocol.transport = sentinel_transport  # type: ignore[attr-defined]

    protocol.scope = {"type": "http"}

    assert protocol.scope == {"type": "http", "transport": sentinel_transport}


def test_client_cert_h11_protocol_scope_setter_accepts_none() -> None:
    """`H11Protocol` resets `self.scope = None` between requests, so the setter must accept it."""
    protocol = object.__new__(ClientCertH11Protocol)
    protocol.transport = object()  # type: ignore[attr-defined]

    protocol.scope = None

    assert protocol.scope is None


def test_openapi_schema_is_gated_by_mtls_like_every_other_route(
    fake_vault: FakeDiagnos, api_settings: ApiSettings
) -> None:
    """`/openapi.json` and `/docs` need a client certificate like every route, as `README.md` promises.

    FastAPI mounts its own schema routes where no dependency reaches them, so `create_app` replaces them with the
    gated ones in `routers/docs.py`.
    """
    ungated = build_app(fake_vault, api_settings, trusted_test_identity=None)
    with TestClient(ungated) as client:
        refused = [client.get(path).status_code for path in ("/openapi.json", "/docs", "/redoc")]
    with TestClient(build_app(fake_vault, api_settings)) as client:
        schema = client.get("/openapi.json")
        swagger = client.get("/docs")

    assert refused == [401, 401, 404]
    assert schema.status_code == 200
    assert "/v1/patients" in schema.json()["paths"]
    assert swagger.status_code == 200
    assert "/openapi.json" in swagger.text
