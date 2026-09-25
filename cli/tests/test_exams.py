"""🇺🇸 `diagnos exams` against the fake `Diagnos` — table rendering, `--json`, decrypted content, mutations.

`test_patients.py` covers the "happy path only" shape of this same command
family; this file goes further and also exercises `--all`, `archive`,
`unarchive`, `delete` (both confirmed and declined), and the create/update
paths that read a record from `--file` — the ones `exams.py`'s own coverage
gap left untouched.

🇧🇷 `diagnos exams` contra a `Diagnos` falsa — renderização de tabela,
`--json`, conteúdo decifrado, mutações.

`test_patients.py` cobre a mesma família de comando só no caminho feliz;
este arquivo vai além e também exercita `--all`, `archive`, `unarchive`,
`delete` (confirmado e recusado), e os caminhos de criar/atualizar que leem
um registro de `--file` — os que a lacuna de cobertura do próprio
`exams.py` deixava intocados.
"""

from __future__ import annotations

import json
from pathlib import Path

from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import EXAM_INDEX, FakeDiagnos


def test_list_exams_renders_table_with_id(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 The table shows the anonymous index — never decrypted content.

    🇧🇷 A tabela mostra o índice anônimo — nunca conteúdo decifrado.
    """
    result = runner.invoke(typer_app, ["exams", "list"])
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output
    assert "Chest CT" not in result.output


def test_list_exams_all_pages_walks_iter_all(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--all` takes the `iter_all` branch instead of one `list` page — still lands the same index.

    🇧🇷 `--all` toma o ramo `iter_all` em vez de uma página de `list` — ainda assim mostra o mesmo índice.
    """
    result = runner.invoke(typer_app, ["exams", "list", "--all"])
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output


def test_get_exam_shows_decrypted_title(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `get` is the one command that ever prints decrypted exam content.

    🇧🇷 `get` é o único comando que chega a imprimir conteúdo decifrado do exame.
    """
    result = runner.invoke(typer_app, ["exams", "get", EXAM_INDEX.document_id, "--version", "v1"])
    assert result.exit_code == 0
    assert "Chest CT" in result.output


def test_get_exam_json_is_valid(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` on `get` bypasses `rich` entirely — a plain `json.loads` round-trips it.

    🇧🇷 `--json` no `get` ignora o `rich` por completo — um `json.loads` puro consegue ler de volta.
    """
    result = runner.invoke(typer_app, ["--json", "exams", "get", EXAM_INDEX.document_id])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["record"]["title"] == "Chest CT"


def test_create_exam_from_file(runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path) -> None:
    """🇺🇸 `--file` reads a JSON record off disk instead of assembling one from inline flags.

    🇧🇷 `--file` lê um registro JSON do disco em vez de montar um a partir de flags inline.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({"title": "Brain MRI"}), encoding="utf-8")
    result = runner.invoke(
        typer_app,
        ["exams", "create", "--patient", "pat_1", "--group", "sg_oncology", "--file", str(record_file)],
    )
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output


def test_create_exam_inline_title(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Without `--file`, `--title` alone is enough to assemble a record.

    🇧🇷 Sem `--file`, só o `--title` já basta para montar um registro.
    """
    result = runner.invoke(
        typer_app,
        ["exams", "create", "--patient", "pat_1", "--group", "sg_oncology", "--modality", "CT", "--title", "Chest CT"],
    )
    assert result.exit_code == 0
    assert "Chest CT" in result.output


def test_update_exam_from_file(runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path) -> None:
    """🇺🇸 `update` reuses the exam's DEK — the CLI only ever reads a fresh record from `--file`.

    🇧🇷 `update` reusa a DEK do exame — a CLI só lê um registro novo de `--file`.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({"title": "Chest CT, revised"}), encoding="utf-8")
    result = runner.invoke(typer_app, ["exams", "update", EXAM_INDEX.document_id, "--file", str(record_file)])
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output


def test_archive_exam_renders_index(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `archive` prints the resulting index panel, never re-fetches decrypted content.

    🇧🇷 `archive` imprime o painel do índice resultante, nunca busca conteúdo decifrado de novo.
    """
    result = runner.invoke(typer_app, ["exams", "archive", EXAM_INDEX.document_id])
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output


def test_unarchive_exam_renders_index(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `unarchive` mirrors `archive`'s rendering. 🇧🇷 `unarchive` espelha a renderização do `archive`."""
    result = runner.invoke(typer_app, ["exams", "unarchive", EXAM_INDEX.document_id])
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output


def test_delete_exam_with_yes_flag_skips_prompt(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--yes` skips the confirmation and deletes outright.

    🇧🇷 `--yes` pula a confirmação e apaga direto.
    """
    result = runner.invoke(typer_app, ["exams", "delete", EXAM_INDEX.document_id, "--yes"])
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output


def test_delete_exam_confirmed_interactively(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Typing `y` at the prompt has the same effect as `--yes`.

    🇧🇷 Digitar `y` no prompt tem o mesmo efeito de `--yes`.
    """
    result = runner.invoke(typer_app, ["exams", "delete", EXAM_INDEX.document_id], input="y\n")
    assert result.exit_code == 0
    assert EXAM_INDEX.document_id in result.output


def test_delete_exam_declined_never_calls_delete(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Typing `n` exits `0` without ever rendering the post-delete index panel.

    🇧🇷 Digitar `n` sai com `0` sem nunca renderizar o painel do índice pós-apagar.
    """
    result = runner.invoke(typer_app, ["exams", "delete", EXAM_INDEX.document_id], input="n\n")
    assert result.exit_code == 0
    assert "exams" not in result.output.lower()
