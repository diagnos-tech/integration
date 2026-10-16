"""🇺🇸 `diagnos login`: hidden input, CRC before the network, `whoami`, then the keyring — else OpenBao, else refusal.

The keyring and OpenBao are in-memory stand-ins; the CRC check, the
store choice and the refusal are the real SDK code. The token text must
never reach stdout or stderr.

🇧🇷 `diagnos login`: entrada oculta, CRC antes da rede, `whoami`, depois o chaveiro — senão o OpenBao, senão recusa.

O chaveiro e o OpenBao são substitutos em memória; a conferência do CRC, a
escolha do cofre e a recusa são o código de verdade do SDK. O texto do token
nunca pode chegar à stdout nem à stderr.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hvac  # type: ignore[import-untyped]
import keyring
import pytest
from keyring.backends import null
from typer.testing import CliRunner

from diagnos import TokenError, TokenStoreError
from diagnos.cli.main import typer_app

from .conftest import FakeDiagnos, mint_token

VAULT = "https://vault.diagnos.health"


class Platform:
    """🇺🇸 A keyring that passes for a platform backend, in a dict. 🇧🇷 Um chaveiro que passa por de plataforma."""

    def __init__(self) -> None:
        """🇺🇸 Empty. 🇧🇷 Vazio."""
        self.items: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, user: str) -> str | None:
        """🇺🇸 Read. 🇧🇷 Leitura."""
        return self.items.get((service, user))

    def set_password(self, service: str, user: str, password: str) -> None:
        """🇺🇸 Write. 🇧🇷 Escrita."""
        self.items[(service, user)] = password

    def delete_password(self, service: str, user: str) -> None:
        """🇺🇸 Delete. 🇧🇷 Remoção."""
        del self.items[(service, user)]


Platform.__module__ = "keyring.backends.macOS"


@pytest.fixture
def platform(monkeypatch: pytest.MonkeyPatch) -> Platform:
    """🇺🇸 The process keyring is a secure, empty one. 🇧🇷 O chaveiro do processo é seguro e vazio."""
    backend = Platform()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    return backend


def _login(runner: CliRunner, text: str, *args: str) -> Any:
    """🇺🇸 `diagnos [args] login` with `text` pasted at the hidden prompt. 🇧🇷 Com `text` colado no prompt oculto."""
    return runner.invoke(typer_app, [*args, "login"], input=f"{text}\n")


def test_login_proves_the_token_and_keeps_it_in_the_keyring(
    runner: CliRunner, patched_build_client: FakeDiagnos, platform: Platform, tmp_path: Path
) -> None:
    """🇺🇸 `whoami` ran (the fake unlocked), the keyring holds the token under the vault URL, nothing echoed.

    🇧🇷 O `whoami` rodou (o falso desbloqueou), o chaveiro guarda o token sob a URL do cofre, nada ecoado.
    """
    text = mint_token()
    result = _login(runner, text)
    assert result.exit_code == 0, result.output
    assert platform.items == {("diagnos", VAULT): text}
    assert patched_build_client.lock_calls == 1 and patched_build_client.close_calls == 1
    assert "keyring (keyring.backends.macOS.Platform)" in result.output
    assert "sg_oncology" in result.output and "svc_" in result.output
    assert text not in result.output and text[8:40] not in result.output


def test_login_as_json_says_what_it_proved_and_where_it_stored(
    runner: CliRunner, patched_build_client: FakeDiagnos, platform: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 One JSON document: the `whoami` fields, `stored_in`, and the variables that would shadow it.

    🇧🇷 Um documento JSON: os campos do `whoami`, `stored_in`, e as variáveis que o esconderiam.
    """
    result = _login(runner, mint_token(), "--json")
    data = json.loads(result.output[result.output.index("{") :])
    assert (data["key_id"], data["stored_in"], data["shadowed_by"]) == (
        patched_build_client.key_id,
        "keyring (keyring.backends.macOS.Platform)",
        [],
    )
    monkeypatch.setenv("DIAGNOS_TOKEN", mint_token())
    shadowed = _login(runner, mint_token())
    assert "DIAGNOS_TOKEN is set in this shell and wins over the stored token" in shadowed.output


def test_a_token_pasted_wrong_stops_before_the_network_and_is_not_stored(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, platform: Platform
) -> None:
    """🇺🇸 The CRC fails first: no client is built, nothing is stored, the message says truncated.

    🇧🇷 O CRC falha primeiro: nenhum client é construído, nada é guardado, a mensagem diz truncado.
    """
    import diagnos.cli.context as context_module

    monkeypatch.setattr(context_module, "build_client", lambda *a, **k: pytest.fail("network · rede"))
    text = mint_token()
    result = _login(runner, text[:-5])
    assert isinstance(result.exception, TokenError)
    assert "truncated or was pasted wrong" in str(result.exception)
    assert platform.items == {}
    legacy = _login(runner, "apikey-header.payload.signature")
    assert isinstance(legacy.exception, TokenError) and "DIAGNOS_API_TOKEN" in str(legacy.exception)


def test_without_a_secure_keyring_it_goes_to_openbao(
    runner: CliRunner, fake_vault: FakeDiagnos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 A `null` keyring does not count; with `OPENBAO_ADDR`, the token lands in OpenBao's `<prefix>/token`.

    The proving session never auto-unseals: the OpenBao token of the
    `login` container may only write the diagnos token.

    🇧🇷 Um chaveiro `null` não conta; com `OPENBAO_ADDR`, o token vai para o `<prefixo>/token` do OpenBao.

    A sessão de prova nunca faz auto-unseal: o token do OpenBao do container
    `login` só pode gravar o token do diagnos.
    """
    import diagnos.cli.context as context_module

    built: list[Any] = []
    monkeypatch.setattr(context_module, "build_client", lambda *a, **k: built.append(k) or fake_vault)
    written: dict[str, Any] = {}

    class Bao:
        """🇺🇸 Just the KV v2 write. 🇧🇷 Só a escrita KV v2."""

        def __init__(self, **kwargs: Any) -> None:
            self.secrets = self.kv = self.v2 = self

        def create_or_update_secret(self, *, path: str, secret: dict[str, Any], mount_point: str) -> None:
            written[f"{mount_point}/{path}"] = secret

    monkeypatch.setattr(keyring, "get_keyring", null.Keyring)
    monkeypatch.setattr(hvac, "Client", Bao)
    monkeypatch.setenv("OPENBAO_ADDR", "https://bao.example")
    monkeypatch.setenv("OPENBAO_TOKEN", "s.writer")
    text = mint_token()
    result = _login(runner, text)
    assert result.exit_code == 0, result.output
    assert written["secret/diagnos/token"]["token"] == text
    assert "OpenBao https://bao.example secret/diagnos/token" in result.output
    assert built == [{"auto_unseal": False}]


def test_with_neither_it_refuses_and_writes_no_file(
    runner: CliRunner, patched_build_client: FakeDiagnos, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """🇺🇸 No secure keyring and no OpenBao: `TokenStoreError` with both options; the home directory stays empty.

    🇧🇷 Sem chaveiro seguro e sem OpenBao: `TokenStoreError` com as duas opções; o diretório do usuário fica vazio.
    """
    monkeypatch.setattr(keyring, "get_keyring", null.Keyring)
    monkeypatch.setenv("HOME", str(tmp_path))
    result = _login(runner, mint_token())
    assert isinstance(result.exception, TokenStoreError)
    assert "OPENBAO_ADDR" in str(result.exception) and "DIAGNOS_TOKEN" in str(result.exception)
    assert list(tmp_path.iterdir()) == []
