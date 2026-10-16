"""🇺🇸 Where `diagnos-api` gets the service account token: OpenBao in a deployment, `DIAGNOS_TOKEN` in CI.

`create_app` without a `vault` builds the real `Diagnos()` — no network
until the lifespan unlocks — so these tests see exactly what the process
would run with. OpenBao is an in-memory `hvac.Client`; the token is minted
from random bytes and never leaves the test.

🇧🇷 De onde o `diagnos-api` tira o token de conta de serviço: OpenBao num deployment, `DIAGNOS_TOKEN` em CI.

`create_app` sem `vault` constrói o `Diagnos()` de verdade — sem rede até o
lifespan desbloquear — então estes testes veem exatamente o que o processo
rodaria. O OpenBao é um `hvac.Client` em memória; o token é criado de bytes
aleatórios e nunca sai do teste.
"""

from __future__ import annotations

import secrets
from typing import Any

import hvac  # type: ignore[import-untyped]
import keyring
import pytest
from keyring.backends import fail

from diagnos import ConfigError
from diagnos.api.app import create_app
from diagnos.api.settings import ApiSettings
from diagnos.crypto.secure import SecretBox
from diagnos.crypto.token_keys import encode_token

_ADDR = "http://openbao:8200"


def _mint(workspace_id: str) -> str:
    """🇺🇸 A fresh token for `workspace_id` — a fixture, never a real secret. 🇧🇷 Um token novo — fixture."""
    seed = SecretBox.from_bytes(bytearray(secrets.token_bytes(32)))
    return encode_token(f"svc_{secrets.token_hex(16)}", seed, workspace_id)


class _Bao:
    """🇺🇸 KV v2 reads over a dict, recording the path and the OpenBao token used. 🇧🇷 Leituras KV v2 sobre um dict."""

    def __init__(self, stored: dict[str, dict[str, Any]], reads: list[tuple[str, str]], **kwargs: Any) -> None:
        """🇺🇸 `kwargs` are `hvac.Client`'s (`url`, `token`, `namespace`). 🇧🇷 Os do `hvac.Client`."""
        self.secrets = self.kv = self.v2 = self
        self._stored, self._reads, self._token = stored, reads, kwargs.get("token")

    def read_secret_version(self, *, path: str, mount_point: str, **_: Any) -> dict[str, Any]:
        """🇺🇸 `InvalidPath` when nothing is there, like OpenBao. 🇧🇷 `InvalidPath` quando não há nada."""
        self._reads.append((f"{mount_point}/{path}", str(self._token)))
        if f"{mount_point}/{path}" not in self._stored:
            raise hvac.exceptions.InvalidPath
        return {"data": {"data": self._stored[f"{mount_point}/{path}"]}}


@pytest.fixture(autouse=True)
def _server_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A server: no token variables, no keyring, OpenBao at `_ADDR` with a read-only token.

    🇧🇷 Um servidor: sem variáveis de token, sem chaveiro, OpenBao em `_ADDR` com um token só de leitura.
    """
    for name in ("DIAGNOS_TOKEN", "DIAGNOS_API_TOKEN", "OPENBAO_TOKEN_FILE", "OPENBAO_MOUNT", "OPENBAO_PATH_PREFIX"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(keyring, "get_keyring", fail.Keyring)
    monkeypatch.setenv("OPENBAO_ADDR", _ADDR)
    monkeypatch.setenv("OPENBAO_TOKEN", "s.reader")


def _openbao(monkeypatch: pytest.MonkeyPatch, stored: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    """🇺🇸 Installs the fake OpenBao over `stored`; the reads it will see. 🇧🇷 Instala o OpenBao falso; as leituras."""
    reads: list[tuple[str, str]] = []
    monkeypatch.setattr(hvac, "Client", lambda **kwargs: _Bao(stored, reads, **kwargs))
    return reads


def test_the_api_reads_the_token_from_openbao(monkeypatch: pytest.MonkeyPatch, api_settings: ApiSettings) -> None:
    """🇺🇸 Nothing in the environment: the token comes from `secret/diagnos/token`, read with the API's own token.

    🇧🇷 Nada no ambiente: o token vem de `secret/diagnos/token`, lido com o token da própria API.
    """
    text = _mint("wsDeploy")
    reads = _openbao(monkeypatch, {"secret/diagnos/token": {"v": 1, "token": text, "saved_at": 0}})
    vault = create_app(api_settings).state.vault
    assert (vault.workspace_id, vault.token_kind) == ("wsDeploy", "hybrid")
    assert vault.token_source == f"OpenBao {_ADDR} secret/diagnos/token"
    assert reads == [("secret/diagnos/token", "s.reader")]
    assert text[8:] not in repr(vault)


def test_diagnos_token_wins_over_openbao_for_ci(monkeypatch: pytest.MonkeyPatch, api_settings: ApiSettings) -> None:
    """🇺🇸 `DIAGNOS_TOKEN` set (CI, an ephemeral container): OpenBao is not even read.

    🇧🇷 `DIAGNOS_TOKEN` definida (CI, um container efêmero): o OpenBao nem é lido.
    """
    reads = _openbao(monkeypatch, {"secret/diagnos/token": {"v": 1, "token": _mint("wsStored"), "saved_at": 0}})
    monkeypatch.setenv("DIAGNOS_TOKEN", _mint("wsCi"))
    vault = create_app(api_settings).state.vault
    assert (vault.workspace_id, vault.token_source) == ("wsCi", "DIAGNOS_TOKEN")
    assert reads == []


def test_without_a_token_the_api_refuses_to_start(monkeypatch: pytest.MonkeyPatch, api_settings: ApiSettings) -> None:
    """🇺🇸 OpenBao reachable but empty: `ConfigError` (exit 2 in `main.run`) naming `diagnos login`, not a crash.

    🇧🇷 OpenBao alcançável mas vazio: `ConfigError` (saída 2 no `main.run`) citando `diagnos login`, não uma quebra.
    """
    _openbao(monkeypatch, {})
    with pytest.raises(ConfigError, match="diagnos login"):
        create_app(api_settings)
