"""🇺🇸 `diagnos groups` — the security groups this enrollment holds a DEK for, or the "none granted" message.

🇧🇷 `diagnos groups` — os security groups para os quais este enrollment tem
uma DEK, ou a mensagem "nenhum concedido".
"""

from __future__ import annotations

import json

from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import FakeDiagnos


def test_groups_lists_each_granted_group(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `groups` unlocks first, then prints one security group id per line.

    🇧🇷 `groups` desbloqueia primeiro, depois imprime um id de security group por linha.
    """
    result = runner.invoke(typer_app, ["groups"])
    assert result.exit_code == 0
    assert patched_build_client._unlocked is True
    assert "sg_oncology" in result.output


def test_groups_json_output(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` emits `{"security_groups": [...]}, parseable straight off stdout.

    🇧🇷 `--json` emite `{"security_groups": [...]}`, parseável direto da stdout.
    """
    result = runner.invoke(typer_app, ["--json", "groups"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["security_groups"] == ["sg_oncology"]


def test_groups_shows_none_granted_message(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 An empty grant list is not an error — it prints the dimmed "none granted" line.

    🇧🇷 Uma lista de concessão vazia não é erro — imprime a linha esmaecida "nenhum concedido".
    """
    patched_build_client.granted_groups = []
    result = runner.invoke(typer_app, ["groups"])
    assert result.exit_code == 0
    assert "No security groups granted · Nenhum security group concedido" in result.output


def test_groups_json_with_none_granted_is_an_empty_list(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` with nothing granted is still `{"security_groups": []}`, never an error or a null.

    🇧🇷 `--json` sem nada concedido ainda é `{"security_groups": []}`, nunca um erro ou um null.
    """
    patched_build_client.granted_groups = []
    result = runner.invoke(typer_app, ["--json", "groups"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["security_groups"] == []
