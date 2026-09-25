"""🇺🇸 `diagnos files` against the fake drive — decrypted names, upload batches, download to a path.

🇧🇷 `diagnos files` contra o drive falso — nomes decifrados, lotes de upload, download para um caminho.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import DRIVE_NODE, FakeDiagnos


def test_list_files_shows_decrypted_name(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 The table column is the plaintext name `Drive.name_of` decrypts, not the sealed `encrypted_name`.

    🇧🇷 A coluna da tabela é o nome em claro que `Drive.name_of` decifra, não o `encrypted_name` selado.
    """
    result = runner.invoke(typer_app, ["files", "list", "--group", "sg_oncology"])
    assert result.exit_code == 0
    assert "chest_ct.dcm" in result.output
    assert DRIVE_NODE.node_id in result.output


def test_upload_files_renders_result_table(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `upload` on one path still goes through the batch path (`upload_many`) and prints the resulting node.

    🇧🇷 `upload` com um único path ainda passa pelo caminho de lote (`upload_many`) e imprime o nó resultante.
    """
    source = tmp_path / "scan.dcm"
    source.write_bytes(b"not-real-dicom-bytes")
    result = runner.invoke(typer_app, ["--quiet", "files", "upload", "--group", "sg_oncology", str(source)])
    assert result.exit_code == 0
    assert DRIVE_NODE.node_id in result.output


def test_download_file_writes_destination(runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path) -> None:
    """🇺🇸 `-o` picks the destination; the fake drive's plaintext bytes land there, decrypted.

    🇧🇷 `-o` escolhe o destino; os bytes em claro do drive falso chegam lá, decifrados.
    """
    destination = tmp_path / "out.dcm"
    result = runner.invoke(
        typer_app,
        ["--quiet", "files", "download", "--group", "sg_oncology", DRIVE_NODE.node_id, "-o", str(destination)],
    )
    assert result.exit_code == 0
    assert destination.read_bytes() == b"fake-encrypted-then-decrypted-bytes"


def test_list_files_all_pages_walks_iter_all(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--all` takes the `iter_all` branch instead of one `list` page.

    🇧🇷 `--all` toma o ramo `iter_all` em vez de uma página de `list`.
    """
    result = runner.invoke(typer_app, ["files", "list", "--group", "sg_oncology", "--all"])
    assert result.exit_code == 0
    assert DRIVE_NODE.node_id in result.output


def test_list_files_json_is_valid(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` on `files list` emits parseable JSON with the decrypted-name-bearing items.

    🇧🇷 `--json` em `files list` emite JSON parseável com os itens carregando o nome decifrado.
    """
    result = runner.invoke(typer_app, ["--json", "files", "list", "--group", "sg_oncology"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["items"][0]["node_id"] == DRIVE_NODE.node_id


def test_upload_files_without_quiet_still_renders_progress_and_result(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 Without `--quiet`, `upload` drives a `rich.progress.Progress` bar — still lands the same result table.

    🇧🇷 Sem `--quiet`, `upload` conduz uma barra `rich.progress.Progress` —
    ainda assim chega à mesma tabela de resultado.
    """
    source = tmp_path / "scan.dcm"
    source.write_bytes(b"not-real-dicom-bytes")
    result = runner.invoke(typer_app, ["files", "upload", "--group", "sg_oncology", str(source)])
    assert result.exit_code == 0
    assert DRIVE_NODE.node_id in result.output


def test_upload_files_rejects_a_path_that_is_not_a_file(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 A directory (or any non-file path) is refused before `build_client`/`upload_many` ever run.

    🇧🇷 Um diretório (ou qualquer path que não seja arquivo) é recusado antes de `build_client`/`upload_many` rodarem.
    """
    result = runner.invoke(typer_app, ["files", "upload", "--group", "sg_oncology", str(tmp_path)])
    assert result.exit_code != 0
    assert "not a file" in result.output


def test_download_file_default_destination_uses_decrypted_name(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 Without `-o`, the destination is `Drive.name_of`'s decrypted name — never the opaque `node_id`.

    🇧🇷 Sem `-o`, o destino é o nome decifrado de `Drive.name_of` — nunca o `node_id` opaco.
    """
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(typer_app, ["files", "download", "--group", "sg_oncology", DRIVE_NODE.node_id])
    assert result.exit_code == 0
    assert (tmp_path / "chest_ct.dcm").read_bytes() == b"fake-encrypted-then-decrypted-bytes"
    assert "Saved · Salvo:" in result.output


def test_download_file_json_reports_saved_to(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 `--json` on `download` reports `node_id`/`saved_to` instead of the human "Saved" line.

    🇧🇷 `--json` em `download` reporta `node_id`/`saved_to` em vez da linha humana "Saved".
    """
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(typer_app, ["--json", "files", "download", "--group", "sg_oncology", DRIVE_NODE.node_id])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["node_id"] == DRIVE_NODE.node_id
    assert data["saved_to"] == "chest_ct.dcm"


def test_get_file_shows_decrypted_name(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `files get` prints the node's metadata plus its decrypted name — never its content.

    🇧🇷 `files get` imprime o metadado do nó mais o nome decifrado — nunca o conteúdo.
    """
    result = runner.invoke(typer_app, ["files", "get", DRIVE_NODE.node_id, "--group", "sg_oncology"])
    assert result.exit_code == 0
    assert "chest_ct.dcm" in result.output


def test_get_file_json_is_valid(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` on `files get` is parseable and carries the same `node_id`.

    🇧🇷 `--json` em `files get` é parseável e carrega o mesmo `node_id`.
    """
    result = runner.invoke(typer_app, ["--json", "files", "get", DRIVE_NODE.node_id, "--group", "sg_oncology"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["node_id"] == DRIVE_NODE.node_id
