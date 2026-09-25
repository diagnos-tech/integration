"""🇺🇸 `diagnos login` calls `unlock()` and shows the granted groups; `--token` is never echoed anywhere.

🇧🇷 `diagnos login` chama `unlock()` e mostra os grupos concedidos; `--token` nunca é ecoado em lugar nenhum.
"""

from __future__ import annotations

import json

from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import FakeDiagnos


def test_login_unlocks_and_shows_groups(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `FakeDiagnos.security_groups` is empty until `unlock()` runs — asserting on it proves `login` called it.

    🇧🇷 `FakeDiagnos.security_groups` fica vazio até `unlock()` rodar — checar isto prova que `login` o chamou.
    """
    result = runner.invoke(typer_app, ["login"])
    assert result.exit_code == 0
    assert patched_build_client._unlocked is True
    assert "sg_oncology" in result.output


def test_login_json_reports_workspace_account_and_groups(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` skips the `rich` banner entirely and emits the same three fields as parseable JSON.

    🇧🇷 `--json` ignora o banner `rich` por completo e emite os mesmos três campos como JSON parseável.
    """
    result = runner.invoke(typer_app, ["--json", "login"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {
        "workspace_id": "ws_1",
        "account_id": "acct_1",
        "security_groups": ["sg_oncology"],
    }


def test_login_never_echoes_token(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 A secret passed as `--token` must never reach stdout/stderr, in any command's output.

    🇧🇷 Um segredo passado como `--token` nunca pode chegar em stdout/stderr, na saída de comando nenhum.
    """
    secret = "apikey-super-secret-do-not-print"  # noqa: S105 — a fixture literal, not a real credential
    result = runner.invoke(typer_app, ["--token", secret, "login"])
    assert result.exit_code == 0
    assert secret not in result.output
