"""🇺🇸 `diagnos` lines in the docs are parsed against the CLI, and `--help` is held to `cli.json` both ways.

🇧🇷 Linhas `diagnos` da doc são interpretadas contra a CLI, e o `--help` é cobrado do `cli.json` nos dois sentidos.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from scripts.docs import cli
from scripts.docs.cli_check import command_lines, help_problems, usage_problem


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    """🇺🇸 `cli.json` as the code produces it now. 🇧🇷 O `cli.json` como o código o produz agora."""
    return cli.build()


def test_command_lines_find_diagnos_in_pipes_subshells_and_continuations() -> None:
    """🇺🇸 Every command position, continuations joined. 🇧🇷 Toda posição de comando, continuações juntas."""
    text = """```sh
diagnos --json patients list --all | jq .
FOLDER=$(diagnos --json files mkdir "CT" --group sg | jq -r .node_id)
diagnos files upload --group sg \\
  scans/IM-0001.dcm
pip install diagnos-cli
```
"""
    assert [(line, " ".join(command.split())) for line, command in command_lines(text)] == [
        (2, "diagnos --json patients list --all"),
        (3, 'diagnos --json files mkdir "CT" --group sg'),
        (4, "diagnos files upload --group sg scans/IM-0001.dcm"),
    ]


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ("diagnos --json patients list --all --summary", None),
        ("diagnos patients get PATIENT_ID --version VERSION_ID", None),
        ('diagnos patients create --group sg --legal-name "Jane Doe" --display-name Jane --tag a --tag b', None),
        ("diagnos files download NODE_ID -o scan.dcm", None),
        ("diagnos login --no-auto-unseal", None),
        ("diagnos patients list --json", "unknown option '--json'"),
        ("diagnos patient list", "unknown command"),
        ("diagnos files upload --grup sg a.dcm", "unknown option '--grup'"),
    ],
)
def test_usage_follows_the_real_command_tree(document: dict[str, Any], line: str, problem: str | None) -> None:
    """🇺🇸 Global options go first; option values are skipped by type. 🇧🇷 Opções globais primeiro; valores pulados."""
    found = usage_problem(line, document)
    assert (found is None) if problem is None else (found is not None and problem in found)


def test_help_agrees_with_the_generated_reference(document: dict[str, Any]) -> None:
    """🇺🇸 Nothing missing either way. 🇧🇷 Nada faltando em nenhum sentido."""
    assert help_problems(document) == []


def test_a_dropped_option_or_command_is_caught(document: dict[str, Any]) -> None:
    """🇺🇸 The check fails when the reference omits what `--help` shows. 🇧🇷 Falha quando a referência omite algo."""
    tampered = copy.deepcopy(document)
    root = tampered["commands"][0]
    root["params"] = [param for param in root["params"] if param["name"] != "quiet"]
    tampered["commands"] = [c for c in tampered["commands"] if c["path"] != ["groups"]]
    problems = help_problems(tampered)
    assert any("'--quiet'" in problem for problem in problems)
    assert any("subcommand 'groups' missing from cli.json" in problem for problem in problems)
