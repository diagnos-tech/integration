"""🇺🇸 `diagnos files` against the fake drive — decrypted names, upload batches, download to a path.

🇧🇷 `diagnos files` contra o drive falso — nomes decifrados, lotes de upload, download para um caminho.
"""

from __future__ import annotations

from pathlib import Path

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
