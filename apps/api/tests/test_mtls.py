"""🇺🇸 mTLS is the only authentication: no certificate is a 401, a disallowed CN is a 403, config demands both PEMs.

Also pins one known gap: `/openapi.json`/`/docs` are not actually gated by
mTLS the way `README.md` claims (`test_openapi_schema_is_gated_by_mtls_like_every_other_route`,
marked `xfail`) — see that test's own docstring.

🇧🇷 mTLS é a única autenticação: sem certificado é 401, um CN não permitido é 403, a configuração exige os dois PEMs.

Também trava uma lacuna conhecida: `/openapi.json`/`/docs` não são de fato
travados por mTLS como o `README.md` promete
(`test_openapi_schema_is_gated_by_mtls_like_every_other_route`, marcado
`xfail`) — veja a docstring desse próprio teste.
"""

from __future__ import annotations

import dataclasses
import ssl
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from diagnos_api.mtls import ClientCertH11Protocol, _identity_from_request, ssl_config_for_uvicorn
from diagnos_api.settings import ApiConfigError, ApiSettings

from conftest import TRUSTED_IDENTITY, FakeDiagnos, build_app


def test_missing_certificate_is_rejected_with_401(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """🇺🇸 No `trusted_test_identity` and no real TLS handshake (`TestClient`) means no identity at all.

    🇧🇷 Sem `trusted_test_identity` e sem handshake TLS de verdade (`TestClient`) significa nenhuma identidade.
    """
    app = build_app(fake_vault, api_settings, trusted_test_identity=None)

    with TestClient(app) as client:
        response = client.get("/v1/session")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "client_certificate_required"


def test_disallowed_cn_is_rejected_with_403(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """🇺🇸 `TRUSTED_IDENTITY.common_name` ("ci-client") is not in `allowed_client_cns` — the allowlist wins.

    🇧🇷 `TRUSTED_IDENTITY.common_name` ("ci-client") não está em `allowed_client_cns` — a lista permitida vence.
    """
    restricted_settings = dataclasses.replace(api_settings, allowed_client_cns=frozenset({"other"}))
    app = build_app(fake_vault, restricted_settings)

    with TestClient(app) as client:
        response = client.get("/v1/session")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "client_certificate_cn_not_allowed"


def test_allowed_cn_passes_through(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """🇺🇸 An empty allowlist (the default) or a matching one both let `TRUSTED_IDENTITY` through.

    🇧🇷 Uma lista vazia (o padrão) ou uma que bate deixam `TRUSTED_IDENTITY` passar.
    """
    allowed = frozenset({TRUSTED_IDENTITY.common_name})
    permissive_settings = dataclasses.replace(api_settings, allowed_client_cns=allowed)
    app = build_app(fake_vault, permissive_settings)

    with TestClient(app) as client:
        response = client.get("/v1/session")

    assert response.status_code == 200
    assert response.json()["client"]["common_name"] == TRUSTED_IDENTITY.common_name


def test_ssl_config_requires_client_certificates(api_settings: ApiSettings) -> None:
    """🇺🇸 `ssl_cert_reqs=CERT_REQUIRED` is what makes the TLS handshake itself refuse an anonymous client.

    🇧🇷 `ssl_cert_reqs=CERT_REQUIRED` é o que faz o próprio handshake TLS recusar um cliente anônimo.
    """
    config = ssl_config_for_uvicorn(api_settings)

    assert config["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert config["ssl_certfile"] == api_settings.tls_cert_file
    assert config["ssl_keyfile"] == api_settings.tls_key_file
    assert config["ssl_ca_certs"] == api_settings.mtls_ca_file


def test_settings_from_env_requires_the_ca_file() -> None:
    """🇺🇸 Without `DIAGNOS_API_MTLS_CA_FILE` (and the cert/key), the process has nothing safe to start with.

    🇧🇷 Sem `DIAGNOS_API_MTLS_CA_FILE` (e o cert/key), o processo não tem nada seguro para subir.
    """
    with pytest.raises(ApiConfigError, match="DIAGNOS_API_MTLS_CA_FILE"):
        ApiSettings.from_env({})


def _request_with_transport(transport: Any) -> SimpleNamespace:
    """🇺🇸 `_identity_from_request` only ever reads `request.scope.get("transport")` — a `SimpleNamespace` is enough.

    🇧🇷 `_identity_from_request` só lê `request.scope.get("transport")` — um `SimpleNamespace` já basta.
    """
    return SimpleNamespace(scope={"transport": transport})


class _FakeTransport:
    """🇺🇸 Stands in for `asyncio.Transport.get_extra_info("ssl_object")` — the one call `_identity_from_request` makes.

    🇧🇷 Substitui `asyncio.Transport.get_extra_info("ssl_object")` — a única chamada que `_identity_from_request` faz.
    """

    def __init__(self, ssl_object: Any) -> None:
        self._ssl_object = ssl_object

    def get_extra_info(self, name: str) -> Any:
        assert name == "ssl_object"
        return self._ssl_object


class _FakeSslObject:
    """🇺🇸 Stands in for `ssl.SSLObject`, only `getpeercert()` — the one method `_identity_from_request` calls.

    🇧🇷 Substitui `ssl.SSLObject`, só `getpeercert()` — o único método que `_identity_from_request` chama.
    """

    def __init__(self, cert: dict[str, Any] | None) -> None:
        self._cert = cert

    def getpeercert(self) -> dict[str, Any] | None:
        return self._cert


def test_identity_from_request_is_none_without_a_transport_in_scope() -> None:
    """🇺🇸 A plain ASGI request with no `transport` key (the normal shape `TestClient` produces) yields no identity.

    🇧🇷 Uma requisição ASGI simples sem a chave `transport` (a forma normal que o `TestClient` produz) não dá identidade.
    """
    request = SimpleNamespace(scope={})

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_is_none_without_an_ssl_object() -> None:
    """🇺🇸 A plain-TCP transport (`get_extra_info("ssl_object")` returns `None`) is not an mTLS connection.

    🇧🇷 Um transporte TCP puro (`get_extra_info("ssl_object")` devolve `None`) não é uma conexão mTLS.
    """
    request = _request_with_transport(_FakeTransport(ssl_object=None))

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_is_none_for_an_empty_peer_certificate() -> None:
    """🇺🇸 `getpeercert()` returning `{}` (TLS negotiated, but no certificate to inspect) is also "no identity".

    🇧🇷 `getpeercert()` devolvendo `{}` (TLS negociado, mas sem certificado para inspecionar) também é "sem identidade".
    """
    request = _request_with_transport(_FakeTransport(_FakeSslObject({})))

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_is_none_without_a_common_name() -> None:
    """🇺🇸 A certificate whose `subject` carries no `commonName` RDN cannot become a `ClientIdentity`.

    🇧🇷 Um certificado cujo `subject` não carrega RDN `commonName` não pode virar uma `ClientIdentity`.
    """
    cert = {"subject": ((("organizationName", "Example Corp"),),), "serialNumber": "01"}
    request = _request_with_transport(_FakeTransport(_FakeSslObject(cert)))

    assert _identity_from_request(request) is None  # type: ignore[arg-type]


def test_identity_from_request_reads_common_name_and_serial() -> None:
    """🇺🇸 A well-formed peer certificate becomes a `ClientIdentity` carrying its `commonName`/`serialNumber`.

    🇧🇷 Um certificado de par bem formado vira uma `ClientIdentity` carregando o `commonName`/`serialNumber` dele.
    """
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
    """🇺🇸 Before any request is parsed, the patched `scope` property reads back `None`.

    🇧🇷 Antes de qualquer requisição ser interpretada, a property `scope` remendada lê `None`.
    """
    protocol = object.__new__(ClientCertH11Protocol)

    assert protocol.scope is None


def test_client_cert_h11_protocol_scope_setter_stamps_the_transport() -> None:
    """🇺🇸 Assigning a new scope dict stamps this connection's `transport` into it, so it survives into the request.

    🇧🇷 Atribuir um dict de scope novo carimba o `transport` desta conexão nele, para sobreviver até a requisição.
    """
    protocol = object.__new__(ClientCertH11Protocol)
    sentinel_transport = object()
    protocol.transport = sentinel_transport  # type: ignore[attr-defined]

    protocol.scope = {"type": "http"}

    assert protocol.scope == {"type": "http", "transport": sentinel_transport}


def test_client_cert_h11_protocol_scope_setter_accepts_none() -> None:
    """🇺🇸 `H11Protocol` resets `self.scope = None` between requests — the setter must not choke on that.

    🇧🇷 O `H11Protocol` reseta `self.scope = None` entre requisições — o setter não pode engasgar com isso.
    """
    protocol = object.__new__(ClientCertH11Protocol)
    protocol.transport = object()  # type: ignore[attr-defined]

    protocol.scope = None

    assert protocol.scope is None


@pytest.mark.xfail(
    strict=True,
    reason="BUG: /openapi.json and /docs are served with no client certificate at all, though README.md says "
    "they are 'reachable only with a valid client certificate, like everything else' (apps/api/app.py never "
    "adds require_client_certificate as a dependency of the FastAPI app itself, only of each router's own routes, "
    "so FastAPI's auto-mounted schema/docs routes skip it entirely)",
)
def test_openapi_schema_is_gated_by_mtls_like_every_other_route(
    fake_vault: FakeDiagnos, api_settings: ApiSettings
) -> None:
    """🇺🇸 `README.md` promises `/openapi.json` needs a client certificate too — today, it does not.

    Every route this API defines by hand takes `Depends(require_client_certificate)`
    explicitly (`routers/*.py`), but `/openapi.json`/`/docs`/`/redoc` are
    routes FastAPI itself adds to `app` — `create_app` never passes
    `dependencies=[Depends(require_client_certificate)]` to `FastAPI(...)`
    (`app.py`), so those three are wide open to anyone who can reach the
    port at all, TLS client certificate or not. That is a real schema
    disclosure gap against this API's own documented security model, not
    just a stale README line.

    🇧🇷 O `README.md` promete que `/openapi.json` também precisa de
    certificado de cliente — hoje, não precisa.

    Toda rota que esta API define à mão recebe
    `Depends(require_client_certificate)` explicitamente (`routers/*.py`),
    mas `/openapi.json`/`/docs`/`/redoc` são rotas que o próprio FastAPI
    acrescenta a `app` — `create_app` nunca passa
    `dependencies=[Depends(require_client_certificate)]` para `FastAPI(...)`
    (`app.py`), então essas três ficam abertas para qualquer um que alcance
    a porta, com ou sem certificado de cliente TLS. Isso é uma lacuna real de
    divulgação de schema contra o próprio modelo de segurança documentado
    desta API, não só uma linha de README desatualizada.
    """
    app = build_app(fake_vault, api_settings, trusted_test_identity=None)

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 401
