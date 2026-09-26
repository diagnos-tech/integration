"""🇺🇸 Global options anywhere on the line, and the entry point that applies them before anything else.

🇧🇷 Opções globais em qualquer lugar da linha, e o ponto de entrada que as aplica antes de tudo.
"""

from __future__ import annotations

import json
import sys

import pytest
from diagnos_cli import main
from diagnos_cli.argv import hoist_global_options

from .conftest import FakeDiagnos


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["patients", "list", "--json"], ["--json", "patients", "list"]),
        (["patients", "get", "p1", "-q", "--no-color"], ["-q", "--no-color", "patients", "get", "p1"]),
        (["groups", "--token", "t", "--vault-url=https://x"], ["--token", "t", "--vault-url=https://x", "groups"]),
        (["--json", "groups"], ["--json", "groups"]),
        (["files", "upload", "a.dcm", "-g", "sg_1"], ["files", "upload", "a.dcm", "-g", "sg_1"]),
        (["files", "upload", "--", "--json"], ["files", "upload", "--", "--json"]),
        (["groups", "--token"], ["--token", "groups"]),
        (["--token", "--json", "groups"], ["--token", "--json", "groups"]),
        ([], []),
    ],
    ids=[
        "flag-after-subcommand",
        "several-flags-keep-order",
        "options-with-values",
        "already-in-front",
        "subcommand-options-stay",
        "after-double-dash-untouched",
        "value-missing-left-to-typer",
        "flag-looking-value-is-a-value",
        "empty",
    ],
)
def test_hoist_global_options(argv: list[str], expected: list[str]) -> None:
    """🇺🇸 Global options (and their values) move to the front; everything else keeps its place.

    🇧🇷 Opções globais (e seus valores) vão para a frente; todo o resto fica onde estava.
    """
    assert hoist_global_options(argv) == expected


def test_app_accepts_json_after_the_subcommand(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], patched_build_client: FakeDiagnos
) -> None:
    """🇺🇸 `diagnos patients list --json` works end to end through the console-script entry point.

    🇧🇷 `diagnos patients list --json` funciona de ponta a ponta pelo ponto de entrada do console-script.
    """
    monkeypatch.setattr(sys, "argv", ["diagnos", "patients", "list", "--json"])
    with pytest.raises(SystemExit) as exited:
        main.app()
    assert exited.value.code == 0
    assert "pat_1" in json.dumps(json.loads(capsys.readouterr().out)["items"])


def test_app_returns_the_agents_exit_code_without_running_here(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 When the agent ran the command, its exit code is final — nothing runs a second time in this process.

    🇧🇷 Quando o agente rodou o comando, o código de saída dele é o final — nada roda de novo neste processo.
    """
    seen: list[list[str]] = []
    monkeypatch.setattr(sys, "argv", ["diagnos", "groups", "--json"])
    monkeypatch.setattr(main, "dispatch", lambda argv: seen.append(argv) or 7)
    monkeypatch.setattr(main, "run", lambda argv: pytest.fail("ran in-process · rodou no processo"))
    with pytest.raises(SystemExit) as exited:
        main.app()
    assert exited.value.code == 7
    assert seen == [["--json", "groups"]]


def test_run_reports_usage_errors_as_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `run` turns Click's own `SystemExit` into a return value, so the agent can relay it.

    🇧🇷 O `run` transforma o `SystemExit` do próprio Click num valor de retorno, para o agente repassá-lo.
    """
    assert main.run(["no-such-command"]) == 2
    assert "No such command" in capsys.readouterr().err
