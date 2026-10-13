"""🇺🇸 The base command line: help, routing, global flags anywhere, and the full CLI's commands as a hint.

🇧🇷 A linha de comando base: ajuda, roteamento, flags globais em qualquer lugar, e os comandos da CLI completa como dica.
"""

from __future__ import annotations

import json

import pytest

from diagnos import __version__
from diagnos._wrapper import main
from diagnos._wrapper.exit_codes import EXIT_OK, EXIT_UNAVAILABLE, EXIT_USAGE

from conftest import Packages

pytestmark = pytest.mark.usefixtures("packages")


@pytest.mark.parametrize("argv", [[], ["--help"], ["-h"], ["help"], ["help", "help"], ["--no-color"]])
def test_every_way_to_ask_for_help_shows_the_overview(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 The four commands and the three things `setup` installs. 🇧🇷 Os quatro comandos e as três coisas do `setup`."""
    assert main(argv) == EXIT_OK
    text = capsys.readouterr().out
    assert f"diagnos {__version__}" in text
    assert all(f"  {name} " in text for name in ("docs", "version", "setup", "help"))
    assert all(f"diagnos setup {target}" in text for target in ("sdk", "cli", "api"))


def test_help_of_one_command_is_its_options(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `diagnos help setup` shows `--dry-run`. 🇧🇷 O `diagnos help setup` mostra o `--dry-run`."""
    assert main(["help", "setup"]) == EXIT_OK
    assert "--dry-run" in capsys.readouterr().out


def test_version_flag_is_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Same as the full CLI's `--version`. 🇧🇷 Igual ao `--version` da CLI completa."""
    assert main(["--version"]) == EXIT_OK
    assert capsys.readouterr().out == f"diagnos {__version__}\n"


@pytest.mark.parametrize("argv", [["--json", "version"], ["version", "--json"]])
def test_global_flags_go_before_or_after_the_command(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 As in the full CLI. 🇧🇷 Como na CLI completa."""
    assert main(argv) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["diagnos"] == __version__


def test_docs_routes_with_its_options(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `diagnos docs dev`. 🇧🇷 `diagnos docs dev`."""
    assert main(["docs", "dev"]) == EXIT_OK
    assert capsys.readouterr().out == "https://dev.diagnos.health\n"


def test_a_full_cli_command_says_how_to_get_it(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `diagnos login` on the base: the install line and `69`.

    🇧🇷 `diagnos login` na base: a linha de instalação e `69`.
    """
    assert main(["login"]) == EXIT_UNAVAILABLE
    error = capsys.readouterr().err
    assert "`diagnos login` is part of the full command line" in error and "diagnos setup cli" in error


def test_an_unknown_option_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 A typo, not a missing layer. 🇧🇷 Um erro de digitação, não uma camada ausente."""
    assert main(["--jsno"]) == EXIT_USAGE
    assert "--jsno" in capsys.readouterr().err


def test_a_bad_option_inside_a_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 argparse's own message, without exiting the process. 🇧🇷 A mensagem do argparse, sem sair do processo."""
    assert main(["docs", "nowhere"]) == EXIT_USAGE
    assert "invalid choice" in capsys.readouterr().err


def test_a_command_help_flag_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `diagnos docs --help` exits `0`. 🇧🇷 O `diagnos docs --help` sai com `0`."""
    assert main(["docs", "--help"]) == EXIT_OK
    assert "--open" in capsys.readouterr().out


def test_setup_without_a_target_lists_the_targets(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 A usage error that teaches the three choices. 🇧🇷 Um erro de uso que ensina as três escolhas."""
    assert main(["setup"]) == EXIT_USAGE
    assert "{sdk,cli,api}" in capsys.readouterr().out


def test_setup_routes_to_its_target(monkeypatch: pytest.MonkeyPatch, packages: Packages) -> None:
    """🇺🇸 Flags reach the plan as given. 🇧🇷 As flags chegam ao plano como dadas."""
    seen: list[tuple[str, bool, bool]] = []
    monkeypatch.setattr(
        "diagnos._wrapper.app.setup",
        lambda target, *, assume_yes, dry_run, out: seen.append((target, assume_yes, dry_run)) or EXIT_OK,
    )
    assert main(["setup", "cli", "-y", "--dry-run"]) == EXIT_OK
    assert seen == [("cli", True, True)]
