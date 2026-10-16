"""🇺🇸 `context.py` itself — the one thing every other `apps/cli/tests` file monkeypatches away.

`build_client` and `enrollment_progress` never run for real anywhere else in
this suite (`conftest.py`'s own docstring: every command test replaces
`build_client` with a fake). This file is where their real bodies get
exercised: `build_client`'s env-override merge, and `enrollment_progress`'s
panel-plus-spinner choreography around a real `on_prompt` call.

🇧🇷 O próprio `context.py` — a única coisa que todo outro arquivo de
`apps/cli/tests` neutraliza com monkeypatch.

`build_client` e `enrollment_progress` nunca rodam de verdade em nenhum
outro lugar desta suíte (a própria docstring do `conftest.py`: todo teste de
comando substitui `build_client` por um falso). Este arquivo é onde o corpo
de verdade deles é exercitado: a fusão de sobrescritas de ambiente do
`build_client`, e a coreografia painel-mais-spinner do `enrollment_progress`
ao redor de uma chamada de `on_prompt` de verdade.
"""

from __future__ import annotations

import base64
import io
import json
from unittest.mock import MagicMock

import keyring
import pytest
from rich.console import Console

from diagnos import ConfigError, EnrollmentPrompt
from diagnos.cli import context
from diagnos.cli.context import CliOptions

from .conftest import mint_token


def _fake_token(*, workspace_id: str = "ws_ctx", account_id: str = "acct_ctx") -> str:
    """🇺🇸 A syntactically valid `apikey-<jwt>` `ServiceAccountToken.parse` accepts — signature never checked.

    🇧🇷 Um `apikey-<jwt>` sintaticamente válido que `ServiceAccountToken.parse` aceita — assinatura nunca é conferida.
    """
    payload = {"sub": "key_1", "account_id": account_id, "workspace_id": workspace_id, "name": "svc@ws.diagnos.health"}
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"apikey-header.{encoded_payload}.signature"


def test_build_client_options_override_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `--token`/`--vault-url` win over whatever `DIAGNOS_API_TOKEN`/`DIAGNOS_VAULT_URL` already say.

    🇧🇷 `--token`/`--vault-url` vencem o que `DIAGNOS_API_TOKEN`/`DIAGNOS_VAULT_URL` já diziam.
    """
    monkeypatch.setenv("DIAGNOS_API_TOKEN", _fake_token(workspace_id="ws_from_env"))
    monkeypatch.delenv("DIAGNOS_VAULT_URL", raising=False)
    options = CliOptions(token=_fake_token(workspace_id="ws_from_flag"), vault_url="https://vault.example.test")

    vault = context.build_client(options)

    assert vault.workspace_id == "ws_from_flag"


def test_build_client_falls_back_to_the_environment_without_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 With no `--token`/`--vault-url`, `build_client` reads exactly what `Settings.from_env()` would.

    🇧🇷 Sem `--token`/`--vault-url`, `build_client` lê exatamente o que `Settings.from_env()` leria.
    """
    monkeypatch.setenv("DIAGNOS_API_TOKEN", _fake_token(workspace_id="ws_env_only"))
    monkeypatch.delenv("DIAGNOS_VAULT_URL", raising=False)

    vault = context.build_client(CliOptions())

    assert vault.workspace_id == "ws_env_only"


def test_enrollment_progress_shows_panel_and_drives_the_spinner_when_not_quiet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 A real `on_prompt` call renders the link/code panel and starts the spinner, stopped only at exit.

    🇧🇷 Uma chamada de verdade a `on_prompt` renderiza o painel de link/código
    e inicia o spinner, parado só na saída.
    """
    console = Console(file=io.StringIO(), width=100, no_color=True)
    fake_status = MagicMock()
    monkeypatch.setattr(console, "status", lambda *args, **kwargs: fake_status)
    prompt = EnrollmentPrompt(
        enrollment_id="enr_1", approval_url="https://vault.test/approve/enr_1", code="AB12", expires_at=0
    )

    with context.enrollment_progress(console, quiet=False) as on_prompt:
        on_prompt(prompt)
        assert fake_status.start.called
        assert not fake_status.stop.called

    assert fake_status.stop.called
    rendered = console.file.getvalue()
    assert "https://vault.test/approve/enr_1" in rendered
    assert "A  B  1  2" in rendered


def test_enrollment_progress_never_starts_the_spinner_when_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `quiet=True` still shows the panel (a human needs the code) but never starts or stops a spinner.

    🇧🇷 `quiet=True` ainda mostra o painel (uma pessoa precisa do código) mas nunca inicia nem para um spinner.
    """
    console = Console(file=io.StringIO(), width=100, no_color=True)
    fake_status = MagicMock()
    monkeypatch.setattr(console, "status", lambda *args, **kwargs: fake_status)
    prompt = EnrollmentPrompt(
        enrollment_id="enr_2", approval_url="https://vault.test/approve/enr_2", code="ZZ99", expires_at=0
    )

    with context.enrollment_progress(console, quiet=True) as on_prompt:
        on_prompt(prompt)

    assert not fake_status.start.called
    assert not fake_status.stop.called
    assert "https://vault.test/approve/enr_2" in console.file.getvalue()


def test_the_cli_takes_the_token_from_the_environment_or_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `DIAGNOS_TOKEN` needs no flag; `--token dgn_sk1_…` wins over it; a token in the legacy variable is refused.

    🇧🇷 `DIAGNOS_TOKEN` não precisa de flag; `--token dgn_sk1_…` vence; um token na variável legada é recusado.
    """
    monkeypatch.setenv("DIAGNOS_TOKEN", mint_token("ws_env"))
    vault = context.build_client(CliOptions())
    assert (vault.workspace_id, vault.token_kind, vault.token_source) == ("ws_env", "hybrid", "DIAGNOS_TOKEN")
    assert context.build_client(CliOptions(token=mint_token("ws_flag"))).workspace_id == "ws_flag"
    monkeypatch.delenv("DIAGNOS_TOKEN")
    monkeypatch.setenv("DIAGNOS_API_TOKEN", mint_token())
    with pytest.raises(ConfigError, match="put it in DIAGNOS_TOKEN"):
        context.build_client(CliOptions())


def test_the_cli_reads_the_keyring_that_login_filled(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Unlike a library call on a mapping, the CLI always looks in the system keyring.

    🇧🇷 Diferente de uma chamada de biblioteca sobre um mapeamento, a CLI sempre procura no chaveiro do sistema.
    """
    stored = {("diagnos", "https://vault.example.test"): mint_token("ws_stored")}
    namespace = {
        "__module__": "keyring.backends.macOS",
        "get_password": lambda self, service, user: stored.get((service, user)),
    }
    backend = type("Keyring", (), namespace)()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    vault = context.build_client(CliOptions(vault_url="https://vault.example.test"))
    assert (vault.workspace_id, vault.token_source) == ("ws_stored", "keyring")


@pytest.mark.parametrize(("tty", "quiet", "hinted"), [(True, False, True), (False, False, False), (True, True, False)])
def test_a_token_from_the_environment_of_a_terminal_gets_one_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tty: bool, quiet: bool, hinted: bool
) -> None:
    """🇺🇸 Interactive and not `--quiet`: one hint towards `diagnos login`, once per run; never in CI or scripts.

    🇧🇷 Interativo e sem `--quiet`: uma dica para o `diagnos login`, uma vez por execução; nunca em CI ou script.
    """
    monkeypatch.setattr(context, "_environment_hinted", False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: tty)
    monkeypatch.setattr("sys.stderr.isatty", lambda: tty)
    monkeypatch.setenv("DIAGNOS_TOKEN", mint_token())
    context.build_client(CliOptions(quiet=quiet))
    context.build_client(CliOptions(quiet=quiet))
    err = capsys.readouterr().err
    assert err.count("DIAGNOS_TOKEN is meant for CI and containers") == (1 if hinted else 0)
    context.hint_environment_token("keyring", quiet=False)
    assert capsys.readouterr().err == ""
