"""🇺🇸 `diagnos status` — identity from the token alone, `--check` for a real unlock, `_memory_label`'s two branches.

🇧🇷 `diagnos status` — identidade só do token, `--check` para um unlock de
verdade, os dois ramos de `_memory_label`.
"""

from __future__ import annotations

import json

import pytest
from diagnos_cli import commands
from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import FakeDiagnos


@pytest.fixture
def fixed_memory_status(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """🇺🇸 A deterministic `memory_status()` stand-in — the real one depends on this host's `mlock` limits.

    Patched onto `diagnos_cli.commands.status` (the name that module bound
    at import time), not `diagnos`, for the same reason `conftest.py`
    patches `context.build_client` rather than a per-command alias.

    🇧🇷 Um substituto determinístico de `memory_status()` — o de verdade
    depende dos limites de `mlock` deste host.

    Aplicado em `diagnos_cli.commands.status` (o nome que aquele módulo
    vinculou na importação), não em `diagnos`, pela mesma razão de
    `conftest.py` aplicar o patch em `context.build_client` em vez de um
    alias por comando.
    """
    summary = {
        "backend": "mlock",
        "lock_policy": "strict",
        "live_secrets": 0,
        "unlocked_allocations": 0,
        "guard_pages": True,
        "wipe_on_fork": True,
    }
    monkeypatch.setattr(commands.status, "memory_status", lambda: summary)
    return summary


def test_status_without_check_never_unlocks(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Without `--check`, `status` never touches the network — `_unlocked` stays `False`.

    🇧🇷 Sem `--check`, `status` nunca toca a rede — `_unlocked` continua `False`.
    """
    result = runner.invoke(typer_app, ["status"])
    assert result.exit_code == 0
    assert patched_build_client._unlocked is False
    assert "workspace_id: ws_1" in result.output
    assert "groups" not in result.output.lower()


def test_status_json_without_check_omits_security_groups(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` without `--check` never adds the `security_groups` key at all.

    🇧🇷 `--json` sem `--check` nunca acrescenta a chave `security_groups`.
    """
    result = runner.invoke(typer_app, ["--json", "status"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["workspace_id"] == "ws_1"
    assert "security_groups" not in data


def test_status_check_unlocks_and_lists_groups(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--check` is the one flag that makes `status` call `unlock()`.

    🇧🇷 `--check` é a única flag que faz `status` chamar `unlock()`.
    """
    result = runner.invoke(typer_app, ["status", "--check"])
    assert result.exit_code == 0
    assert patched_build_client._unlocked is True
    assert "sg_oncology" in result.output


def test_status_check_json_includes_security_groups(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json --check` is the one combination that adds `security_groups` to the payload.

    🇧🇷 `--json --check` é a única combinação que acrescenta `security_groups` ao payload.
    """
    result = runner.invoke(typer_app, ["--json", "status", "--check"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["security_groups"] == ["sg_oncology"]


def test_status_reports_openbao_configured(
    runner: CliRunner, patched_build_client: FakeDiagnos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 `OPENBAO_ADDR` set in the environment flips the `openbao_configured` field.

    🇧🇷 `OPENBAO_ADDR` setada no ambiente vira o campo `openbao_configured`.
    """
    monkeypatch.setenv("OPENBAO_ADDR", "https://openbao.example.test")
    result = runner.invoke(typer_app, ["status"])
    assert result.exit_code == 0
    assert "configured · configurado" in result.output


def test_status_reports_openbao_not_set(
    runner: CliRunner, patched_build_client: FakeDiagnos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 Without `OPENBAO_ADDR`, the same field reads "not set".

    🇧🇷 Sem `OPENBAO_ADDR`, o mesmo campo lê "não definido".
    """
    monkeypatch.delenv("OPENBAO_ADDR", raising=False)
    result = runner.invoke(typer_app, ["status"])
    assert result.exit_code == 0
    assert "not set · não definido" in result.output


def test_status_memory_label_when_everything_is_locked(
    runner: CliRunner, patched_build_client: FakeDiagnos, fixed_memory_status: dict[str, object]
) -> None:
    """🇺🇸 `unlocked_allocations == 0` is the "everything locked" branch of `_memory_label`.

    🇧🇷 `unlocked_allocations == 0` é o ramo "tudo travado" de `_memory_label`.
    """
    result = runner.invoke(typer_app, ["status"])
    assert result.exit_code == 0
    assert "locked in RAM · travada na RAM (mlock, strict)" in result.output


def test_status_memory_label_when_some_allocations_are_unlocked(
    runner: CliRunner, patched_build_client: FakeDiagnos, fixed_memory_status: dict[str, object]
) -> None:
    """🇺🇸 A positive `unlocked_allocations` switches to the "raise ulimit -l" warning branch.

    🇧🇷 Um `unlocked_allocations` positivo troca para o ramo de aviso "suba o ulimit -l".
    """
    fixed_memory_status["unlocked_allocations"] = 3
    result = runner.invoke(typer_app, ["status"])
    assert result.exit_code == 0
    assert "3 allocation(s) not locked" in result.output
    assert "ulimit -l" in result.output
