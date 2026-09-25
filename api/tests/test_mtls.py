"""🇺🇸 mTLS is the only authentication: no certificate is a 401, a disallowed CN is a 403, config demands both PEMs.

🇧🇷 mTLS é a única autenticação: sem certificado é 401, um CN não permitido é 403, a configuração exige os dois PEMs.
"""

from __future__ import annotations

import dataclasses
import ssl

import pytest
from conftest import TRUSTED_IDENTITY, FakeDiagnos, build_app
from fastapi.testclient import TestClient

from diagnos_api.mtls import ssl_config_for_uvicorn
from diagnos_api.settings import ApiConfigError, ApiSettings


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
