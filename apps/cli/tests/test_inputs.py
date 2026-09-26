"""🇺🇸 `inputs.load_record` — `--file` or inline flags (never both), the file's three failure modes, the fallback.

Every other test file drives this indirectly through `patients`/`exams
create`/`update`; this one calls `load_record` directly so each branch (a
missing file, invalid JSON, a JSON array instead of an object, and the
"nothing given at all" refusal) gets its own unambiguous assertion instead
of being a side effect of some command's happy path.

🇧🇷 `inputs.load_record` — `--file` ou flags inline (nunca os dois), os três
jeitos do arquivo falhar, e o retorno às flags inline.

Todo outro arquivo de teste exercita isto indiretamente via `patients`/
`exams create`/`update`; este chama `load_record` direto para cada ramo
(arquivo ausente, JSON inválido, um array JSON em vez de objeto, e a recusa
"nada foi dado") ganhar a própria asserção inequívoca, em vez de ser efeito
colateral do caminho feliz de algum comando.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from diagnos_cli.inputs import load_record


def test_file_and_inline_fields_together_are_refused(tmp_path: Path) -> None:
    """🇺🇸 `--file` with an inline field is a `BadParameter` naming the flag, never a silent pick.

    🇧🇷 `--file` com um campo inline é um `BadParameter` que nomeia a flag, nunca uma escolha silenciosa.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text('{"legal_name": "Jane Doe"}', encoding="utf-8")
    with pytest.raises(typer.BadParameter, match="--legal-name"):
        load_record(record_file, {"legal_name": "other", "display_name": None})
    assert load_record(record_file, {"legal_name": None}) == {"legal_name": "Jane Doe"}


def test_missing_file_raises_bad_parameter(tmp_path: Path) -> None:
    """🇺🇸 A path that does not exist is an `OSError` from `read_text`, translated into `typer.BadParameter`.

    🇧🇷 Um path que não existe é um `OSError` de `read_text`, traduzido em `typer.BadParameter`.
    """
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(typer.BadParameter, match="cannot read"):
        load_record(missing, {})


def test_invalid_json_raises_bad_parameter(tmp_path: Path) -> None:
    """🇺🇸 A file that exists but is not valid JSON is refused before ever reaching the SDK.

    🇧🇷 Um arquivo que existe mas não é JSON válido é recusado antes de sequer chegar ao SDK.
    """
    bad_json = tmp_path / "record.json"
    bad_json.write_text("{not json", encoding="utf-8")
    with pytest.raises(typer.BadParameter, match="not valid JSON"):
        load_record(bad_json, {})


def test_json_array_is_rejected(tmp_path: Path) -> None:
    """🇺🇸 Valid JSON that is not an object (e.g. a bare array) is also refused.

    🇧🇷 JSON válido que não é um objeto (ex.: um array puro) também é recusado.
    """
    array_json = tmp_path / "record.json"
    array_json.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(typer.BadParameter, match="must contain a JSON object"):
        load_record(array_json, {})


def test_inline_fields_are_used_when_no_file_is_given() -> None:
    """🇺🇸 Without `--file`, the non-`None` inline flags become the record — `None` ones are dropped.

    🇧🇷 Sem `--file`, as flags inline não-`None` viram o registro — as `None` são descartadas.
    """
    result = load_record(None, {"legal_name": "Alice", "display_name": None})
    assert result == {"legal_name": "Alice"}


def test_no_file_and_no_inline_fields_raises_bad_parameter() -> None:
    """🇺🇸 Neither `--file` nor a single inline field: nothing to build a record from.

    🇧🇷 Nem `--file` nem um único campo inline: nada para montar um registro.
    """
    with pytest.raises(typer.BadParameter, match="pass --file"):
        load_record(None, {"legal_name": None})
