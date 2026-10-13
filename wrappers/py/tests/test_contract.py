"""🇺🇸 Conformance: the Python base implements `wrappers/contract.json` exactly — the spec other wrappers copy.

🇧🇷 Conformidade: a base Python implementa exatamente o `wrappers/contract.json` — a especificação dos wrappers.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from diagnos._wrapper import exit_codes
from diagnos._wrapper.app import COMMANDS, _parser
from diagnos._wrapper.docs import LINKS
from diagnos._wrapper.setup import TARGETS
from diagnos._wrapper.setup.image import IMAGE, ISSUER, MIN_COSIGN, TRIGGER, identity
from diagnos._wrapper.setup.tools import INSTALL_PAGES

ROOT = Path(__file__).resolve().parents[3]
CONTRACT: dict[str, Any] = json.loads((ROOT / "wrappers" / "contract.json").read_text(encoding="utf-8"))


def _shape(parser: argparse.ArgumentParser) -> tuple[dict[str, list[str]], set[str]]:
    """🇺🇸 `({argument: choices}, {option strings})` of a parser, without `--help`.

    🇧🇷 O formato de um parser, sem `--help`.
    """
    arguments = {action.dest: list(action.choices or []) for action in parser._actions if not action.option_strings}
    options = {flag for action in parser._actions for flag in action.option_strings} - {"-h", "--help"}
    return arguments, options


@pytest.mark.parametrize("command", sorted(CONTRACT["commands"]))
def test_each_command_takes_exactly_the_contracts_arguments_and_options(command: str) -> None:
    """🇺🇸 Same names, same choices, same flags. 🇧🇷 Mesmos nomes, mesmas escolhas, mesmas flags."""
    arguments, options = _shape(_parser(command))
    assert arguments == CONTRACT["commands"][command]["arguments"]
    assert options == set(CONTRACT["commands"][command]["options"])


def test_the_command_set_is_the_contracts() -> None:
    """🇺🇸 Four commands, no more. 🇧🇷 Quatro comandos, nada mais."""
    assert set(COMMANDS) == set(CONTRACT["commands"]) and CONTRACT["program"] == "diagnos"


def test_links_are_the_contracts_and_the_json_shape() -> None:
    """🇺🇸 `diagnos docs --json` prints `links` verbatim. 🇧🇷 O `diagnos docs --json` imprime `links` ao pé da letra."""
    assert {link.topic: {"name": link.name, "url": link.url} for link in LINKS} == CONTRACT["links"]


def test_setup_targets_image_signer_and_install_pages() -> None:
    """🇺🇸 What is verified, against whom, with what. 🇧🇷 O que é verificado, contra quem, com o quê."""
    setup = CONTRACT["setup"]
    assert set(TARGETS) == set(setup) and setup["api"]["image"] == IMAGE
    assert setup["api"]["signer"]["identity"].format(version="9.9.9") == identity("9.9.9")
    assert setup["api"]["signer"]["issuer"] == ISSUER
    assert setup["api"]["signer"]["trigger"] == TRIGGER
    assert setup["api"]["minimumCosign"] == ".".join(map(str, MIN_COSIGN))
    assert CONTRACT["installPages"] == INSTALL_PAGES


def test_exit_codes_are_the_contracts() -> None:
    """🇺🇸 0, 1, 2, 69. 🇧🇷 0, 1, 2, 69."""
    assert CONTRACT["exitCodes"] == {
        "ok": exit_codes.EXIT_OK,
        "failed": exit_codes.EXIT_FAILED,
        "usage": exit_codes.EXIT_USAGE,
        "unavailable": exit_codes.EXIT_UNAVAILABLE,
    }


def test_package_and_extras_are_pyprojects() -> None:
    """🇺🇸 The distribution name and every extra. 🇧🇷 O nome da distribuição e todo extra."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    assert CONTRACT["package"]["pypi"] == project["name"]
    assert set(CONTRACT["package"]["extras"]) == set(project["optional-dependencies"])
