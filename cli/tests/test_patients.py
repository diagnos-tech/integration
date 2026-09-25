"""🇺🇸 `diagnos patients` against the fake `Diagnos` — table rendering, `--json`, decrypted content.

🇧🇷 `diagnos patients` contra a `Diagnos` falsa — renderização de tabela, `--json`, conteúdo decifrado.
"""

from __future__ import annotations

import json

from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import PATIENT_INDEX, FakeDiagnos


def test_list_patients_renders_table_with_id(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 The table shows the anonymous index (id, dates, groups) — never decrypted content.

    🇧🇷 A tabela mostra o índice anônimo (id, datas, grupos) — nunca conteúdo decifrado.
    """
    result = runner.invoke(typer_app, ["patients", "list"])
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output
    assert "Jane Doe" not in result.output  # 🇺🇸 content, never shown by `list` 🇧🇷 conteúdo, nunca em `list`


def test_list_patients_json_is_valid(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` emits parseable JSON with the same index id, and no rich table markup.

    🇧🇷 `--json` emite JSON parseável com o mesmo id de índice, sem marcação de tabela do rich.
    """
    result = runner.invoke(typer_app, ["--json", "patients", "list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["items"][0]["document_id"] == PATIENT_INDEX.document_id


def test_get_patient_shows_decrypted_legal_name(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `get` is the one command that ever prints decrypted record content.

    🇧🇷 `get` é o único comando que chega a imprimir conteúdo decifrado do registro.
    """
    result = runner.invoke(typer_app, ["patients", "get", PATIENT_INDEX.document_id])
    assert result.exit_code == 0
    assert "Jane Doe" in result.output


def test_create_patient_requires_file_or_inline_field(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Neither `--file` nor an inline field: `inputs.load_record` refuses before any SDK call.

    🇧🇷 Nem `--file` nem um campo inline: `inputs.load_record` recusa antes de qualquer chamada ao SDK.
    """
    result = runner.invoke(typer_app, ["patients", "create", "--group", "sg_oncology"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
