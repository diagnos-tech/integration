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

import pytest
from diagnos import EnrollmentPrompt
from diagnos_cli import context
from diagnos_cli.context import CliOptions
from rich.console import Console


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
