"""🇺🇸 `diagnos patients` against the fake `Diagnos` — table rendering, `--json`, decrypted content.

🇧🇷 `diagnos patients` contra a `Diagnos` falsa — renderização de tabela, `--json`, conteúdo decifrado.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    assert data["items"][0]["index"]["document_id"] == PATIENT_INDEX.document_id


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


def test_create_patient_inline_field_succeeds(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 One inline field (no `--file`) is enough to reach `Patients.create`.

    🇧🇷 Um campo inline (sem `--file`) já basta para chegar em `Patients.create`.
    """
    result = runner.invoke(typer_app, ["patients", "create", "--group", "sg_oncology", "--legal-name", "Alice"])
    assert result.exit_code == 0
    # 🇺🇸 the fake always returns the fixed `PATIENT` 🇧🇷 o fake sempre devolve o `PATIENT` fixo
    assert "Jane Doe" in result.output


def test_get_patient_json_is_valid(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` on `get` prints the decrypted record as parseable JSON, bypassing the `rich` panel.

    🇧🇷 `--json` no `get` imprime o registro decifrado como JSON parseável, ignorando o painel `rich`.
    """
    result = runner.invoke(typer_app, ["--json", "patients", "get", PATIENT_INDEX.document_id])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["record"]["legal_name"] == "Jane Doe"


def test_list_patients_all_pages_walks_iter_all(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--all` takes the `iter_all` branch instead of one `list` page.

    🇧🇷 `--all` toma o ramo `iter_all` em vez de uma página de `list`.
    """
    result = runner.invoke(typer_app, ["patients", "list", "--all"])
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output


def test_update_patient_from_file(runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path) -> None:
    """🇺🇸 `update` reuses the patient's DEK — the CLI only ever reads a fresh record from `--file`.

    🇧🇷 `update` reusa a DEK do paciente — a CLI só lê um registro novo de `--file`.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({"legal_name": "Jane Doe, revised"}), encoding="utf-8")
    result = runner.invoke(typer_app, ["patients", "update", PATIENT_INDEX.document_id, "--file", str(record_file)])
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output


def test_archive_patient_renders_index(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `archive` prints the resulting index panel, never re-fetches decrypted content.

    🇧🇷 `archive` imprime o painel do índice resultante, nunca busca conteúdo decifrado de novo.
    """
    result = runner.invoke(typer_app, ["patients", "archive", PATIENT_INDEX.document_id])
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output


def test_archive_patient_json_is_valid(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` on a mutation (`archive`/`unarchive`/`delete`) prints the index as parseable JSON.

    🇧🇷 `--json` numa mutação (`archive`/`unarchive`/`delete`) imprime o índice como JSON parseável.
    """
    result = runner.invoke(typer_app, ["--json", "patients", "archive", PATIENT_INDEX.document_id])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["document_id"] == PATIENT_INDEX.document_id


def test_unarchive_patient_renders_index(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `unarchive` mirrors `archive`'s rendering. 🇧🇷 `unarchive` espelha a renderização do `archive`."""
    result = runner.invoke(typer_app, ["patients", "unarchive", PATIENT_INDEX.document_id])
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output


def test_delete_patient_with_yes_flag_skips_prompt(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--yes` skips the confirmation and deletes outright.

    🇧🇷 `--yes` pula a confirmação e apaga direto.
    """
    result = runner.invoke(typer_app, ["patients", "delete", PATIENT_INDEX.document_id, "--yes"])
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output


def test_delete_patient_confirmed_interactively(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Typing `y` at the prompt has the same effect as `--yes`.

    🇧🇷 Digitar `y` no prompt tem o mesmo efeito de `--yes`.
    """
    result = runner.invoke(typer_app, ["patients", "delete", PATIENT_INDEX.document_id], input="y\n")
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output


def test_delete_patient_declined_never_renders_the_result(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Typing `n` exits `0` without ever rendering the post-delete index panel.

    🇧🇷 Digitar `n` sai com `0` sem nunca renderizar o painel do índice pós-apagar.
    """
    result = runner.invoke(typer_app, ["patients", "delete", PATIENT_INDEX.document_id], input="n\n")
    assert result.exit_code == 0
    assert "patients" not in result.output.lower()


def test_list_patients_summary_flag_shows_names(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Names (and tags) appear only with `--summary` — the default stays anonymous.

    🇧🇷 Nomes (e tags) só aparecem com `--summary` — o padrão continua anônimo.
    """
    result = runner.invoke(typer_app, ["patients", "list", "--summary"])
    assert result.exit_code == 0
    # 🇺🇸 The runner's 80-column terminal wraps the cell. 🇧🇷 O terminal de 80 colunas do runner quebra a célula.
    assert "Jane" in result.output
    assert "[oncology]" in result.output


def test_create_patient_passes_tags_and_inline_fields(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--tag` is repeatable and `--external-id` joins the record.

    🇧🇷 `--tag` é repetível e `--external-id` entra no registro.
    """
    result = runner.invoke(
        typer_app,
        [
            "patients",
            "create",
            "-g",
            "sg1",
            "--legal-name",
            "Ana",
            "--external-id",
            "mrn-9",
            "--tag",
            "a",
            "--tag",
            "b",
        ],
    )
    assert result.exit_code == 0
    name, kwargs = patched_build_client.patients.calls[-1]
    assert name == "create"
    assert kwargs == {
        "record": {"legal_name": "Ana", "external_id": "mrn-9"},
        "security_group": "sg1",
        "tags": ["a", "b"],
    }


def test_update_patient_tags_and_expect_version(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 No `--tag` keeps the tags (`None`); `--expect-version` is the conflict guard.

    🇧🇷 Sem `--tag` mantém as tags (`None`); `--expect-version` é a trava de conflito.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({"legal_name": "Jane Doe", "display_name": "Jane"}), encoding="utf-8")
    args = ["patients", "update", PATIENT_INDEX.document_id, "--file", str(record_file)]

    runner.invoke(typer_app, args)
    runner.invoke(typer_app, [*args, "--tag", "vip", "--expect-version", "v1"])

    (_, kept), (_, replaced) = patched_build_client.patients.calls[-2:]
    assert kept["tags"] is None
    assert kept["expected_latest_version_id"] is None
    assert replaced["tags"] == ["vip"]
    assert replaced["expected_latest_version_id"] == "v1"


def test_get_patient_committed_flag(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--committed` asks for saved versions only. 🇧🇷 `--committed` pede só versões salvas."""
    runner.invoke(typer_app, ["patients", "get", PATIENT_INDEX.document_id, "--committed"])
    assert patched_build_client.patients.calls[-1] == ("get", {"version_id": None, "include_draft": False})


def test_restore_patient_renders_index(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `restore` takes the patient out of the trash. 🇧🇷 `restore` tira o paciente da lixeira."""
    result = runner.invoke(typer_app, ["patients", "restore", PATIENT_INDEX.document_id])
    assert result.exit_code == 0
    assert PATIENT_INDEX.document_id in result.output
