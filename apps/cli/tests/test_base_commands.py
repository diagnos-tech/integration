"""🇺🇸 `diagnos docs | version | setup | help` in the full CLI: the base's behavior, and the base's options.

🇧🇷 `diagnos docs | version | setup | help` na CLI completa: o comportamento da base, e as opções da base.
"""

from __future__ import annotations

import json

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from diagnos._wrapper.app import _parser
from diagnos.cli.main import typer_app

_GLOBALS = {"--json", "--no-color"}


@pytest.mark.parametrize("name", ["docs", "version", "setup", "help"])
def test_typer_takes_the_same_options_as_the_base(name: str) -> None:
    """🇺🇸 Every base option exists here, on the command or as a global; every argument has the same choices.

    🇧🇷 Toda opção da base existe aqui, no comando ou como global; todo argumento tem as mesmas escolhas.
    """
    root = get_command(typer_app)
    command = root.commands[name]  # type: ignore[attr-defined]
    base = _parser(name)
    flags = {flag for param in command.params for flag in [*param.opts, *param.secondary_opts] if flag.startswith("-")}
    wanted = {flag for action in base._actions for flag in action.option_strings} - {"-h", "--help"}
    assert flags | _GLOBALS == wanted | _GLOBALS
    choices = {
        param.name: sorted(getattr(param.type, "choices", []))
        for param in command.params
        if not param.opts[0].startswith("-")
    }
    expected = {action.dest: sorted(action.choices or []) for action in base._actions if not action.option_strings}
    if name == "help":
        assert set(choices) == set(expected) == {"command"}
    else:
        assert choices == expected


def test_docs_prints_the_bare_url(runner: CliRunner) -> None:
    """🇺🇸 Same as the base. 🇧🇷 Igual à base."""
    result = runner.invoke(typer_app, ["docs", "dev"])
    assert result.exit_code == 0 and result.output == "https://dev.diagnos.health\n"


def test_the_global_json_reaches_the_base(runner: CliRunner) -> None:
    """🇺🇸 `diagnos --json version`. 🇧🇷 `diagnos --json version`."""
    result = runner.invoke(typer_app, ["--json", "version"])
    assert result.exit_code == 0 and json.loads(result.output)["extras"]["cli"] is True


def test_setup_cli_is_already_done_here(runner: CliRunner) -> None:
    """🇺🇸 The full CLI is installed, so nothing runs. 🇧🇷 A CLI completa está instalada, então nada roda."""
    result = runner.invoke(typer_app, ["setup", "cli"])
    assert result.exit_code == 0 and "already installed" in result.output


def test_help_shows_a_commands_help(runner: CliRunner) -> None:
    """🇺🇸 `diagnos help patients list` is `diagnos patients list --help`. 🇧🇷 O mesmo que `--help`."""
    result = runner.invoke(typer_app, ["help", "patients", "list"])
    assert result.exit_code == 0 and "--all" in result.output
    assert "docs" in runner.invoke(typer_app, ["help"]).output
