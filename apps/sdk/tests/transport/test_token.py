"""🇺🇸 `ServiceAccountToken.parse` and the redaction promise on both `Settings` and the token.

The JWT here is entirely synthetic (`fake-signature`, on purpose) because
`parse` never verifies it — the vault does. What this test actually pins is
the claim extraction and the two failure modes a caller can hit by
misconfiguring `DIAGNOS_API_TOKEN`, plus the one property that must hold no
matter what: the raw secret never appears in a `repr`.

🇧🇷 `ServiceAccountToken.parse` e a promessa de redação em `Settings` e no token.

O JWT aqui é totalmente sintético (`fake-signature`, de propósito) porque
`parse` nunca verifica a assinatura — quem verifica é o cofre. O que este
teste trava de fato é a extração de claims e os dois jeitos de falhar que
quem chama pode ter ao configurar `DIAGNOS_API_TOKEN` errado, mais a
propriedade que precisa valer sempre: o segredo cru nunca aparece num `repr`.
"""

from __future__ import annotations

import json

import pytest
from diagnos.crypto.encoding import b64url_encode
from diagnos.errors import ConfigError
from diagnos.transport.config import Settings
from diagnos.transport.token import ServiceAccountToken

_VALID_PAYLOAD = {
    "sub": "key_123",
    "account_id": "acc_1",
    "workspace_id": "ws_1",
    "name": "svc@ws_1.diagnos.health",
}


def _make_apikey(payload: dict[str, object]) -> str:
    """🇺🇸 A syntactically valid `apikey-<jwt>` with an unchecked, fake signature.

    🇧🇷 Um `apikey-<jwt>` sintaticamente válido, com assinatura falsa e não conferida.
    """
    header_b64 = b64url_encode(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))
    signature_b64 = b64url_encode(b"fake-signature")
    return f"apikey-{header_b64}.{payload_b64}.{signature_b64}"


def test_parse_extracts_claims_without_checking_signature() -> None:
    """🇺🇸 `parse` reads every claim; a fake signature does not stop it.

    🇧🇷 `parse` lê toda claim; uma assinatura falsa não o impede.
    """
    raw = _make_apikey(_VALID_PAYLOAD)
    token = ServiceAccountToken.parse(raw)
    assert token.raw == raw
    assert token.key_id == "key_123"
    assert token.account_id == "acc_1"
    assert token.workspace_id == "ws_1"
    assert token.name == "svc@ws_1.diagnos.health"


def test_parse_missing_apikey_prefix_raises_config_error() -> None:
    """🇺🇸 A raw JWT with no `apikey-` prefix is a configuration mistake.

    🇧🇷 Um JWT cru sem prefixo `apikey-` é um erro de configuração.
    """
    with pytest.raises(ConfigError):
        ServiceAccountToken.parse("eyJhbGciOiJFZERTQSJ9.eyJzdWIiOiJrIn0.sig")


def test_parse_wrong_segment_count_raises_config_error() -> None:
    """🇺🇸 A JWT without three dot-separated segments is truncated or corrupted.

    🇧🇷 Um JWT sem três segmentos separados por ponto está truncado ou corrompido.
    """
    with pytest.raises(ConfigError):
        ServiceAccountToken.parse("apikey-only-one-segment")


def test_parse_missing_claim_raises_config_error() -> None:
    """🇺🇸 A payload missing a required claim (`name`) is rejected.

    🇧🇷 Um payload sem uma claim obrigatória (`name`) é rejeitado.
    """
    incomplete = dict(_VALID_PAYLOAD)
    del incomplete["name"]
    with pytest.raises(ConfigError):
        ServiceAccountToken.parse(_make_apikey(incomplete))


def test_parse_non_json_payload_raises_config_error() -> None:
    """🇺🇸 A payload segment that is not base64url JSON is rejected.

    🇧🇷 Um segmento de payload que não é JSON base64url é rejeitado.
    """
    header_b64 = b64url_encode(json.dumps({"alg": "EdDSA"}).encode("utf-8"))
    garbage_payload_b64 = b64url_encode(b"not-json-at-all")
    signature_b64 = b64url_encode(b"sig")
    with pytest.raises(ConfigError):
        ServiceAccountToken.parse(f"apikey-{header_b64}.{garbage_payload_b64}.{signature_b64}")


def test_token_repr_never_contains_raw_secret() -> None:
    """🇺🇸 `repr(token)` shows the redacted form, never the raw `apikey-<jwt>`.

    🇧🇷 `repr(token)` mostra a forma redigida, nunca o `apikey-<jwt>` cru.
    """
    raw = _make_apikey(_VALID_PAYLOAD)
    token = ServiceAccountToken.parse(raw)
    assert raw not in repr(token)
    assert "apikey-…" in repr(token)


def test_authorization_header_carries_the_bearer_token() -> None:
    """🇺🇸 `authorization_header` returns the exact `Bearer apikey-<jwt>` value.

    🇧🇷 `authorization_header` retorna o valor exato `Bearer apikey-<jwt>`.
    """
    raw = _make_apikey(_VALID_PAYLOAD)
    token = ServiceAccountToken.parse(raw)
    assert token.authorization_header() == {"Authorization": f"Bearer {raw}"}


def test_settings_from_env_requires_api_token() -> None:
    """🇺🇸 A missing `DIAGNOS_API_TOKEN` raises `ConfigError`, not a `KeyError`.

    🇧🇷 `DIAGNOS_API_TOKEN` ausente lança `ConfigError`, não um `KeyError`.
    """
    with pytest.raises(ConfigError):
        Settings.from_env({})


def test_settings_from_env_reads_all_variables() -> None:
    """🇺🇸 Every documented env var lands on the matching `Settings` field.

    🇧🇷 Toda env var documentada cai no campo certo de `Settings`.
    """
    settings = Settings.from_env(
        {
            "DIAGNOS_API_TOKEN": "apikey-abc.def.ghi",
            "DIAGNOS_VAULT_URL": "https://vault.example.test",
            "DIAGNOS_TIMEOUT_SECONDS": "5.5",
            "DIAGNOS_TIME_PRECISION": "day",
            "OPENBAO_ADDR": "https://bao.example.test",
            "OPENBAO_TOKEN": "s.supersecrettoken",
            "OPENBAO_MOUNT": "custom-mount",
            "OPENBAO_PATH_PREFIX": "custom-prefix",
            "OPENBAO_NAMESPACE": "team-a",
        }
    )
    assert settings.vault_url == "https://vault.example.test"
    assert settings.timeout_seconds == 5.5
    assert settings.time_precision == "day"
    assert settings.openbao_addr == "https://bao.example.test"
    assert settings.openbao_mount == "custom-mount"
    assert settings.openbao_path_prefix == "custom-prefix"
    assert settings.openbao_namespace == "team-a"


def test_settings_repr_never_contains_raw_secrets() -> None:
    """🇺🇸 `repr(settings)` redacts both `api_token` and `openbao_token`.

    🇧🇷 `repr(settings)` redige tanto `api_token` quanto `openbao_token`.
    """
    settings = Settings.from_env(
        {
            "DIAGNOS_API_TOKEN": "apikey-abc.def.ghi",
            "OPENBAO_TOKEN": "s.supersecrettoken",
        }
    )
    rendered = repr(settings)
    assert "apikey-abc.def.ghi" not in rendered
    assert "s.supersecrettoken" not in rendered
    assert "apikey-…" in rendered
