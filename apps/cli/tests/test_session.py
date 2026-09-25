"""🇺🇸 `diagnos session lock` — always calls `vault.lock()`; the confirmation message respects `--quiet`/`--json`.

🇧🇷 `diagnos session lock` — sempre chama `vault.lock()`; a mensagem de
confirmação respeita `--quiet`/`--json`.
"""

from __future__ import annotations

from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import FakeDiagnos


def test_lock_calls_vault_lock_and_prints_message(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `FakeDiagnos.lock` flips `_unlocked` back to `False` — checking it proves `lock()` really ran.

    🇧🇷 `FakeDiagnos.lock` vira `_unlocked` de volta para `False` — checar isto prova que `lock()` rodou.
    """
    patched_build_client._unlocked = True
    result = runner.invoke(typer_app, ["session", "lock"])
    assert result.exit_code == 0
    assert patched_build_client._unlocked is False
    assert "Session locked · Sessão travada" in result.output


def test_lock_quiet_suppresses_the_message(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--quiet` still locks the session, only the confirmation line is skipped.

    🇧🇷 `--quiet` ainda trava a sessão, só a linha de confirmação é que é pulada.
    """
    result = runner.invoke(typer_app, ["--quiet", "session", "lock"])
    assert result.exit_code == 0
    assert patched_build_client._unlocked is False
    assert "Session locked" not in result.output


def test_lock_json_also_suppresses_the_message(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` alone (no `--quiet`) still suppresses the human-readable line — nothing to parse otherwise.

    🇧🇷 Só `--json` (sem `--quiet`) já suprime a linha legível por humano — senão não haveria o que parsear.
    """
    result = runner.invoke(typer_app, ["--json", "session", "lock"])
    assert result.exit_code == 0
    assert "Session locked" not in result.output
