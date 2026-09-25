"""🇺🇸 `diagnos_cli.render` called directly — the table/panel branches no fixed fake ever produces on its own.

`test_patients.py`/`test_exams.py`/`test_files.py` drive these functions
through real commands, but the fakes in `conftest.py` always hand back the
same flags (never archived, never deleted, no pending version, never an
empty page, never a `next_cursor`). Calling `render_index_table`,
`render_patient`, `render_exam`, `render_document_index`, `human_size` and
the drive-node renderers directly is what reaches those branches without
growing the fakes into something nobody else needs.

🇧🇷 `diagnos_cli.render` chamado direto — os ramos de tabela/painel que
nenhum fake fixo produz sozinho.

`test_patients.py`/`test_exams.py`/`test_files.py` exercitam estas funções
por comandos de verdade, mas os fakes de `conftest.py` sempre devolvem as
mesmas flags (nunca arquivado, nunca apagado, sem versão pendente, nunca uma
página vazia, nunca um `next_cursor`). Chamar `render_index_table`,
`render_patient`, `render_exam`, `render_document_index`, `human_size` e os
renderizadores de nó de drive direto é o que alcança esses ramos sem fazer
os fakes crescerem para algo que mais ninguém precisa.
"""

from __future__ import annotations

import io
import json

import pytest
from diagnos import DocumentListItem, DocumentStream, ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos_cli.render.documents import (
    render_document_index,
    render_exam,
    render_index_table,
    render_patient,
    report_text,
)
from diagnos_cli.render.drives import human_size, render_drive_node, render_drive_node_table
from rich.console import Console

from .conftest import DRIVE_NODE, EXAM, EXAM_INDEX, EXAM_ITEM, PATIENT, PATIENT_ITEM


def _console(width: int = 160) -> Console:
    """🇺🇸 A `rich.Console` writing to an in-memory buffer — no real terminal, no width guesswork.

    🇧🇷 Um `rich.Console` escrevendo num buffer em memória — sem terminal de verdade, sem adivinhar largura.
    """
    return Console(file=io.StringIO(), width=width, no_color=True)


def _text(console: Console) -> str:
    """🇺🇸 Everything printed, with the table's own word-wrap collapsed.

    🇧🇷 Tudo o que foi impresso, sem a quebra da tabela.
    """
    return " ".join(console.file.getvalue().split())  # type: ignore[attr-defined]


def test_render_index_table_shows_every_flag() -> None:
    """🇺🇸 `archived`/`deleted`/`pending`/`draft` render when the index carries them.

    🇧🇷 `archived`/`deleted`/`pending`/`draft` aparecem quando o índice as carrega.
    """
    stream = EXAM_INDEX.stream().model_dump()
    stream["pending_version_id"] = "v2"
    stream["draft"] = {"rev": 1, "size": 9, "updated_at": "2099-01-01T00:00:00.000Z", "updated_by": "u"}
    flagged = EXAM_INDEX.model_copy(
        update={"is_archived": True, "is_deleted": True, "streams": {"data": DocumentStream.model_validate(stream)}}
    )
    console = _console()

    render_index_table(console, [DocumentListItem[ExamSummary](index=flagged)], json_output=False)

    assert "archived, deleted, pending, draft" in _text(console)


def test_render_index_table_hides_the_summary_unless_asked() -> None:
    """🇺🇸 Names stay off the screen by default; `show_summary` adds them (with tags / title · modality).

    🇧🇷 Nomes ficam fora da tela por padrão; `show_summary` os acrescenta (com tags / título · modalidade).
    """
    hidden, shown = _console(), _console()

    render_index_table(hidden, [PATIENT_ITEM, EXAM_ITEM], json_output=False)
    render_index_table(shown, [PATIENT_ITEM, EXAM_ITEM], json_output=False, show_summary=True)

    assert "Jane" not in _text(hidden)
    assert "Jane [oncology]" in _text(shown)
    assert "Chest CT · CT" in _text(shown)
    assert "sg_oncology" in _text(hidden)


def test_render_index_table_summary_edge_cases() -> None:
    """🇺🇸 A missing or empty summary prints `—`, and a legal name stands in for a missing display name.

    🇧🇷 Um resumo ausente ou vazio imprime `—`, e o nome legal substitui um nome de exibição ausente.
    """
    console = _console()
    rows = [
        DocumentListItem[PatientSummary](index=EXAM_INDEX),
        DocumentListItem[ExamSummary](index=EXAM_INDEX, summary=ExamSummary()),
        DocumentListItem[PatientSummary](index=EXAM_INDEX, summary=PatientSummary(legal_name="Maria")),
    ]

    render_index_table(console, rows, json_output=False, show_summary=True)

    assert _text(console).count("—") >= 2
    assert "Maria" in _text(console)


def test_render_index_table_json_adds_the_summary_only_when_asked(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 JSON rows are `{index, summary}` like the HTTP API; `summary` is filled only with `show_summary`.

    🇧🇷 Linhas JSON são `{index, summary}` como na API HTTP; `summary` só é preenchido com `show_summary`.
    """
    render_index_table(_console(), [PATIENT_ITEM], json_output=True)
    plain_rows = json.loads(capsys.readouterr().out)["items"]
    render_index_table(_console(), [PATIENT_ITEM], json_output=True, show_summary=True)
    rich_rows = json.loads(capsys.readouterr().out)["items"]

    assert plain_rows[0]["index"]["document_id"] == PATIENT_ITEM.id
    assert plain_rows[0]["summary"] is None
    assert rich_rows[0]["summary"]["display_name"] == "Jane"


def test_render_index_table_empty_shows_the_no_results_message() -> None:
    """🇺🇸 An empty page is not silently blank — it prints the dimmed "no results" line.

    🇧🇷 Uma página vazia não fica muda — imprime a linha esmaecida "nenhum resultado".
    """
    console = _console()

    render_index_table(console, [], json_output=False)

    assert "No results · Nenhum resultado" in console.file.getvalue()  # type: ignore[attr-defined]


def test_render_index_table_shows_the_next_cursor_hint() -> None:
    """🇺🇸 A non-empty `next_cursor` (one page short of `--all`) prints a resume hint.

    🇧🇷 Um `next_cursor` não vazio (uma página aquém de `--all`) imprime uma dica para retomar.
    """
    console = _console()

    render_index_table(console, [EXAM_ITEM], json_output=False, next_cursor="cursor_abc123")

    assert "cursor_abc123" in console.file.getvalue()  # type: ignore[attr-defined]


def test_render_patient_json_bypasses_rich_and_writes_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `json_output=True` calls `print_json`, which writes straight to `sys.stdout` — never through `console`.

    🇧🇷 `json_output=True` chama `print_json`, que escreve direto na `sys.stdout` — nunca pelo `console`.
    """
    render_patient(_console(), PATIENT, json_output=True)

    data = json.loads(capsys.readouterr().out)
    assert data["record"]["legal_name"] == "Jane Doe"
    assert data["version_id"] == "v1"


def test_render_patient_panel_shows_address_tags_source_and_sealed_identifiers() -> None:
    """🇺🇸 Identifiers show by name only; address in one line; where the content came from.

    🇧🇷 Identificadores só pelo nome; endereço numa linha; de onde veio o conteúdo.
    """
    record = PatientRecord.model_validate(
        {
            "legal_name": "Jane Doe",
            "display_name": "Jane",
            "identifiers": [{"name": "cpf", "value": "secret:v1:a:b:c"}],
            "address": {"street": "Rua A", "number": "10", "city": "Recife", "postal_code": "50000", "country": "BR"},
        }
    )
    console = _console()

    render_patient(console, PATIENT.model_copy(update={"record": record, "draft_rev": 4}), json_output=False)

    text = _text(console)
    assert "cpf (sealed · selado)" in text
    assert "secret:v1" not in text
    assert "Rua A, 10, Recife — 50000 BR" in text
    assert "oncology" in text
    assert "draft · rascunho (rev 4)" in text


def test_render_patient_panel_without_optional_blocks() -> None:
    """🇺🇸 No address, no identifiers, a committed version. 🇧🇷 Sem endereço, sem identificadores, versão confirmada."""
    console = _console()

    render_patient(console, PATIENT.model_copy(update={"summary": None}), json_output=False)

    assert "version · versão v1" in _text(console)


def test_render_exam_shows_the_report_as_plain_text() -> None:
    """🇺🇸 `report_html` is shown as text, one line per block — never as HTML or terminal markup.

    🇧🇷 `report_html` aparece como texto, uma linha por bloco — nunca como HTML ou marcação de terminal.
    """
    html = "<h1>Impression</h1><p>No <b>acute</b> findings [bold]x[/bold].</p><ul><li>one</li><li>two</li></ul>"
    exam = EXAM.model_copy(update={"record": ExamRecord(title="CT", report_html=html)})
    console = _console()

    render_exam(console, exam, json_output=False)

    lines = [line.strip("│ ") for line in console.file.getvalue().splitlines()]  # type: ignore[attr-defined]
    start = lines.index("report: Impression")
    assert lines[start + 1 : start + 4] == ["No acute findings [bold]x[/bold].", "one", "two"]
    assert not [line for line in lines if "<" in line]


def test_report_text_edge_cases() -> None:
    """🇺🇸 No HTML, or HTML with no text, is `None`. 🇧🇷 Sem HTML, ou HTML sem texto, é `None`."""
    assert report_text(None) is None
    assert report_text("<p> </p><br>") is None
    assert report_text("plain") == "plain"


def test_render_exam_panel_fields() -> None:
    """🇺🇸 Title, modality, patient and report status from clear `meta`.

    🇧🇷 Título, modalidade, paciente e status do laudo.
    """
    exam = EXAM.model_copy(
        update={"index": EXAM_INDEX.model_copy(update={"meta": {"patient_id": "pat_1", "report_status": "published"}})}
    )
    console = _console()

    render_exam(console, exam, json_output=False)

    text = _text(console)
    for expected in ("Chest CT", "CT", "pat_1", "published", "No acute findings."):
        assert expected in text


def test_table_cell_with_markup_like_content_is_printed_literally() -> None:
    """🇺🇸 A table cell shaped like `rich` markup prints as-is — every cell goes through `plain()`.

    🇧🇷 Uma célula de tabela com forma de markup `rich` imprime como está — toda célula passa por `plain()`.
    """
    tricky = EXAM_INDEX.model_copy(update={"document_id": "[bold]exam_1[/bold]"})
    summary = ExamSummary(title="[red]CT[/red]")
    console = _console(300)

    render_index_table(
        console, [DocumentListItem[ExamSummary](index=tricky, summary=summary)], json_output=False, show_summary=True
    )

    assert "[bold]exam_1[/bold]" in _text(console)
    assert "[red]CT[/red]" in _text(console)


def test_panel_title_with_markup_like_id_is_printed_literally() -> None:
    """🇺🇸 Panel titles are escaped too. 🇧🇷 Títulos de painel também são escapados."""
    console = _console()

    render_document_index(console, EXAM_INDEX.model_copy(update={"document_id": "[red]x[/red]"}), json_output=False)

    assert "exams [red]x[/red]" in _text(console)


def test_render_document_index_non_json_shows_the_resource_and_flags() -> None:
    """🇺🇸 The non-`--json` panel title is `f"{resource} {document_id}"`, with the group and flags as fields.

    🇧🇷 O título do painel sem `--json` é `f"{resource} {document_id}"`, com grupo e flags como campos.
    """
    console = _console()

    render_document_index(console, EXAM_INDEX, json_output=False)

    text = _text(console)
    assert f"exams {EXAM_INDEX.document_id}" in text
    assert "sg_oncology" in text


@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [
        (None, "—"),
        (0, "0 B"),
        (512, "512 B"),
        (2048, "2.0 KB"),
        (5 * 1024 * 1024, "5.0 MB"),
        (3 * 1024 * 1024 * 1024, "3.0 GB"),
    ],
)
def test_human_size_picks_the_smallest_fitting_unit(num_bytes: int | None, expected: str) -> None:
    """🇺🇸 `None` is `"—"`; otherwise the smallest of B/KB/MB/GB that keeps the number under 1024.

    🇧🇷 `None` é `"—"`; senão, a menor entre B/KB/MB/GB que mantém o número abaixo de 1024.
    """
    assert human_size(num_bytes) == expected


def test_render_drive_node_table_json_bypasses_rich(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `json_output=True` prints `{"items": [{node, name}], "next_cursor"}` straight to `stdout`.

    🇧🇷 `json_output=True` imprime `{"items": [{node, name}], "next_cursor"}` direto na `stdout`.
    """

    class _FixedNameDrive:
        """🇺🇸 Decrypts every name to the same value. 🇧🇷 Decifra todo nome para o mesmo valor."""

        def name_of(self, node: object) -> str:
            """🇺🇸 Always `scan.dcm`. 🇧🇷 Sempre `scan.dcm`."""
            return "scan.dcm"

    render_drive_node_table(_console(), drive=_FixedNameDrive(), nodes=[DRIVE_NODE], json_output=True, next_cursor="c2")

    data = json.loads(capsys.readouterr().out)
    assert data["items"][0]["node"]["node_id"] == DRIVE_NODE.node_id
    assert data["items"][0]["name"] == "scan.dcm"
    assert data["next_cursor"] == "c2"


def test_render_drive_node_table_empty_shows_no_results() -> None:
    """🇺🇸 An empty node list prints the same dimmed "no results" line as an empty document index page.

    🇧🇷 Uma lista de nós vazia imprime a mesma linha esmaecida "nenhum resultado" de uma página de índice vazia.
    """

    class _NoOpDrive:
        """🇺🇸 Never called — `render_drive_node_table` only invokes `name_of` per row, and there are none.

        🇧🇷 Nunca chamado — `render_drive_node_table` só invoca `name_of` por linha, e não há nenhuma.
        """

    console = _console()

    render_drive_node_table(console, drive=_NoOpDrive(), nodes=[], json_output=False)

    assert "No results · Nenhum resultado" in console.file.getvalue()


def test_render_drive_node_non_json_shows_the_decrypted_name() -> None:
    """🇺🇸 `files get`'s panel: `drive.name_of(node)` decrypts the name shown alongside the sealed metadata.

    🇧🇷 O painel do `files get`: `drive.name_of(node)` decifra o nome mostrado junto do metadado selado.
    """

    class _FixedNameDrive:
        """🇺🇸 Always decrypts to the same name — enough for this one assertion.

        🇧🇷 Sempre decifra para o mesmo nome — basta para esta única asserção.
        """

        def name_of(self, node: object) -> str:
            return "chest_ct.dcm"

    console = _console()

    render_drive_node(console, drive=_FixedNameDrive(), node=DRIVE_NODE, json_output=False)

    assert "chest_ct.dcm" in console.file.getvalue()
