"""🇺🇸 `diagnos files` against the fake drive — decrypted names, upload batches, download to a path.

🇧🇷 `diagnos files` contra o drive falso — nomes decifrados, lotes de upload, download para um caminho.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from diagnos_cli import main as main_module
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
        ["--quiet", "files", "download", DRIVE_NODE.node_id, "-o", str(destination)],
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
    assert data["items"][0]["node"]["node_id"] == DRIVE_NODE.node_id
    assert data["items"][0]["name"] == "chest_ct.dcm"
    assert data["next_cursor"] is None


def test_list_files_survives_a_group_without_a_key(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 A row whose group key this session lacks shows 🔒 (JSON `null`) instead of failing the whole list.

    🇧🇷 Uma linha cujo grupo esta sessão não tem chave mostra 🔒 (JSON `null`) em vez de derrubar a lista inteira.
    """
    patched_build_client.drives.locked = True

    table = runner.invoke(typer_app, ["files", "list"])
    as_json = runner.invoke(typer_app, ["--json", "files", "list"])
    panel = runner.invoke(typer_app, ["files", "get", DRIVE_NODE.node_id])

    assert table.exit_code == 0
    assert "🔒" in table.output
    assert json.loads(as_json.output)["items"][0]["name"] is None
    assert panel.exit_code == 0
    assert "🔒" in panel.output


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
    result = runner.invoke(typer_app, ["files", "download", DRIVE_NODE.node_id])
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
    result = runner.invoke(typer_app, ["--json", "files", "download", DRIVE_NODE.node_id])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["node_id"] == DRIVE_NODE.node_id
    assert data["saved_to"] == "chest_ct.dcm"


def test_get_file_shows_decrypted_name(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `files get` prints the node's metadata plus its decrypted name — never its content.

    🇧🇷 `files get` imprime o metadado do nó mais o nome decifrado — nunca o conteúdo.
    """
    result = runner.invoke(typer_app, ["files", "get", DRIVE_NODE.node_id])
    assert result.exit_code == 0
    assert "chest_ct.dcm" in result.output


def test_get_file_json_is_valid(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--json` on `files get` is `{node, name}` — the same shape the API answers.

    🇧🇷 `--json` em `files get` é `{node, name}` — a mesma forma que a API responde.
    """
    result = runner.invoke(typer_app, ["--json", "files", "get", DRIVE_NODE.node_id])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["node"]["node_id"] == DRIVE_NODE.node_id
    assert data["name"] == "chest_ct.dcm"


def test_list_files_filters_reach_the_sdk(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--group` is optional; `--folder`/`--exam`/`--include-pending` become the SDK's filters.

    🇧🇷 `--group` é opcional; `--folder`/`--exam`/`--include-pending` viram os filtros do SDK.
    """
    result = runner.invoke(
        typer_app, ["files", "list", "--folder", "folder_1", "--exam", "exam_1", "--include-pending"]
    )
    assert result.exit_code == 0
    assert patched_build_client.drives.calls[-1] == (
        "list",
        {
            "security_group": None,
            "exam_id": "exam_1",
            "parent_id": "folder_1",
            "include_pending": True,
            "limit": 50,
            "cursor": None,
        },
    )


def test_upload_into_a_folder_and_mkdir(runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path) -> None:
    """🇺🇸 `mkdir` prints the new folder id; `upload --folder` places files in it.

    🇧🇷 `mkdir` imprime o id da pasta nova; `upload --folder` põe arquivos nela.
    """
    source = tmp_path / "a.dcm"
    source.write_bytes(b"x")

    made = runner.invoke(typer_app, ["files", "mkdir", "Series 1", "--group", "sg1", "--parent", "root_1"])
    made_json = runner.invoke(typer_app, ["--json", "files", "mkdir", "Series 2", "--group", "sg1"])
    runner.invoke(typer_app, ["--quiet", "files", "upload", str(source), "--group", "sg1", "--folder", "folder_1"])

    drive = patched_build_client.drives.handed_out["sg1"]
    assert made.output.strip() == "folder_1"
    assert json.loads(made_json.output) == {"node_id": "folder_1"}
    assert drive.calls[0] == ("create_folder", {"name": "Series 1", "parent_id": "root_1"})
    assert drive.calls[-1][1]["parent_id"] == "folder_1"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("chest_ct.dcm", "chest_ct.dcm"),
        ("../../.bashrc", ".bashrc"),
        ("Series 1/IM-1.dcm", "IM-1.dcm"),
        ("C:\\temp\\evil.exe", "evil.exe"),
        ("..", "node_1"),
        (None, "node_1"),
        ("", "node_1"),
        ("   ", "node_1"),
        ("/etc/passwd", "passwd"),
        ("exame_do_tórax_ç.dcm", "exame_do_tórax_ç.dcm"),
    ],
)
def test_download_never_writes_outside_the_current_directory(
    runner: CliRunner,
    patched_build_client: FakeDiagnos,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    expected: str,
) -> None:
    """🇺🇸 The default destination is only the last segment of the decrypted name.

    🇧🇷 O destino padrão é só o último segmento do nome decifrado.
    """
    monkeypatch.chdir(tmp_path)
    patched_build_client.drives.names["node_1"] = name  # type: ignore[assignment]

    result = runner.invoke(typer_app, ["--quiet", "files", "download", DRIVE_NODE.node_id])

    assert result.exit_code == 0
    assert (tmp_path / expected).read_bytes() == b"fake-encrypted-then-decrypted-bytes"


def test_upload_rejects_a_path_that_does_not_exist_at_all(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 A path with no file behind it at all fails the same `is_file()` check as a directory does.

    🇧🇷 Um path sem arquivo nenhum atrás falha a mesma checagem `is_file()` de um diretório.
    """
    missing = tmp_path / "does-not-exist.dcm"

    result = runner.invoke(typer_app, ["files", "upload", "--group", "sg_oncology", str(missing)])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "not a file" in result.output
    assert not patched_build_client.drives.handed_out


def test_upload_and_download_round_trip_a_unicode_file_name(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 A source path with accented/non-ASCII characters uploads; the same characters in a decrypted name download.

    🇧🇷 Um path de origem com caracteres acentuados/não-ASCII sobe; os mesmos
    caracteres num nome decifrado baixam.
    """
    source = tmp_path / "exame_intoxicação_até_39°.dcm"
    source.write_bytes(b"unicode-safe-bytes")

    uploaded = runner.invoke(typer_app, ["--quiet", "files", "upload", "--group", "sg1", str(source)])
    assert uploaded.exit_code == 0
    drive = patched_build_client.drives.handed_out["sg1"]
    assert drive.calls[-1][1]["sources"] == [str(source)]

    monkeypatch.chdir(tmp_path)
    patched_build_client.drives.names["node_1"] = "relatório_ção.dcm"
    downloaded = runner.invoke(typer_app, ["--quiet", "files", "download", "node_1"])
    assert downloaded.exit_code == 0
    assert (tmp_path / "relatório_ção.dcm").read_bytes() == b"fake-encrypted-then-decrypted-bytes"


def test_download_into_an_existing_subdirectory_via_output(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `-o` accepts a nested destination as long as its parent directory already exists.

    🇧🇷 `-o` aceita um destino aninhado desde que o diretório-pai já exista.
    """
    subdir = tmp_path / "series"
    subdir.mkdir()

    result = runner.invoke(typer_app, ["--quiet", "files", "download", "node_1", "-o", str(subdir / "out.dcm")])

    assert result.exit_code == 0
    assert (subdir / "out.dcm").read_bytes() == b"fake-encrypted-then-decrypted-bytes"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG: files.py:download_file / main.py:app() — an -o destination whose parent directory does not "
        "exist raises a raw FileNotFoundError (Drive.download opens the path with Path.open('wb'), no "
        "directory is created and no DiagnosError is raised), which main.app()'s wrapper only catches for "
        "DiagnosError, so this is an uncaught Python traceback instead of a clean, documented exit code."
    ),
)
def test_download_to_a_missing_parent_directory_never_raises_a_raw_traceback(
    monkeypatch: pytest.MonkeyPatch, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `-o some/missing/dir/out.dcm` should fail cleanly, not crash with a Python traceback.

    Goes through `main_module.app()` (the real console-script entry point,
    like `test_errors.py`), not `CliRunner`, because `CliRunner` swallows
    any exception into `result.exception` — a real terminal would not, and
    that is exactly the gap this test is proving.

    🇧🇷 `-o some/missing/dir/out.dcm` deveria falhar de forma limpa, não
    quebrar com um traceback Python.

    Passa por `main_module.app()` (o ponto de entrada de verdade do
    console-script, como em `test_errors.py`), não pelo `CliRunner` —
    `CliRunner` engole qualquer exceção em `result.exception`, um terminal
    de verdade não engoliria, e é exatamente essa lacuna que este teste
    prova.
    """
    destination = tmp_path / "no" / "such" / "dir" / "out.dcm"
    monkeypatch.setattr(sys, "argv", ["diagnos", "--quiet", "files", "download", "node_1", "-o", str(destination)])

    with pytest.raises(SystemExit):
        main_module.app()
