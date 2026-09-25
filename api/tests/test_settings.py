"""🇺🇸 `ApiSettings.from_env`: the full success path, `DIAGNOS_API_PORT` parsing, and the allowed-CN CSV.

`test_mtls.py` already covers the "CA/cert/key missing" refusal
(`ApiConfigError`); this file covers everything `from_env` does once those
three are present — defaults, an explicit host/port, a malformed port, and
the CSV-to-`frozenset` parsing `require_client_certificate` gates on.

🇧🇷 `ApiSettings.from_env`: o caminho de sucesso completo, o parsing de
`DIAGNOS_API_PORT`, e o CSV de CN permitidos.

`test_mtls.py` já cobre a recusa "CA/cert/key ausentes" (`ApiConfigError`);
este arquivo cobre tudo que `from_env` faz uma vez que os três estão
presentes — padrões, host/porta explícitos, uma porta malformada, e o
parsing de CSV para `frozenset` em que `require_client_certificate` se
apoia.
"""

from __future__ import annotations

import pytest

from diagnos_api.settings import DEFAULT_HOST, DEFAULT_PORT, ApiConfigError, ApiSettings


def _base_env() -> dict[str, str]:
    """🇺🇸 The three PEM paths `from_env` cannot start without — never opened, just read as strings.

    🇧🇷 Os três paths de PEM sem os quais `from_env` não sobe — nunca abertos, só lidos como strings.
    """
    return {
        "DIAGNOS_API_MTLS_CA_FILE": "/ca.pem",
        "DIAGNOS_API_TLS_CERT_FILE": "/tls.pem",
        "DIAGNOS_API_TLS_KEY_FILE": "/tls-key.pem",
    }


def test_from_env_defaults_host_and_port_when_unset() -> None:
    """🇺🇸 Without `DIAGNOS_API_HOST`/`DIAGNOS_API_PORT`, the documented `0.0.0.0:8443` defaults apply.

    🇧🇷 Sem `DIAGNOS_API_HOST`/`DIAGNOS_API_PORT`, valem os padrões documentados `0.0.0.0:8443`.
    """
    settings = ApiSettings.from_env(_base_env())

    assert settings.mtls_ca_file == "/ca.pem"
    assert settings.tls_cert_file == "/tls.pem"
    assert settings.tls_key_file == "/tls-key.pem"
    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT
    assert settings.allowed_client_cns == frozenset()


def test_from_env_reads_an_explicit_host_and_port() -> None:
    """🇺🇸 `DIAGNOS_API_HOST`/`DIAGNOS_API_PORT` override the defaults when both are set.

    🇧🇷 `DIAGNOS_API_HOST`/`DIAGNOS_API_PORT` sobrescrevem os padrões quando ambas estão setadas.
    """
    env = {**_base_env(), "DIAGNOS_API_HOST": "127.0.0.1", "DIAGNOS_API_PORT": "9443"}

    settings = ApiSettings.from_env(env)

    assert settings.host == "127.0.0.1"
    assert settings.port == 9443


def test_from_env_rejects_a_non_numeric_port() -> None:
    """🇺🇸 A `DIAGNOS_API_PORT` that is not an integer fails fast, before a socket is ever opened.

    🇧🇷 Um `DIAGNOS_API_PORT` que não é um inteiro falha rápido, antes de qualquer socket abrir.
    """
    env = {**_base_env(), "DIAGNOS_API_PORT": "not-a-port"}

    with pytest.raises(ApiConfigError, match="DIAGNOS_API_PORT"):
        ApiSettings.from_env(env)


def test_from_env_parses_the_allowed_cn_csv() -> None:
    """🇺🇸 A comma-separated `DIAGNOS_API_ALLOWED_CLIENT_CN` becomes a `frozenset`, blanks and spaces trimmed.

    🇧🇷 Um `DIAGNOS_API_ALLOWED_CLIENT_CN` separado por vírgula vira `frozenset`, sem espaços e sem vazios.
    """
    env = {**_base_env(), "DIAGNOS_API_ALLOWED_CLIENT_CN": " ci-client , other-client ,,"}

    settings = ApiSettings.from_env(env)

    assert settings.allowed_client_cns == frozenset({"ci-client", "other-client"})
