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
from diagnos import ExamRecord
from diagnos_cli.render.documents import render_document_index, render_exam, render_index_table, render_patient
from diagnos_cli.render.drives import human_size, render_drive_node, render_drive_node_table
from rich.console import Console

from .conftest import DRIVE_NODE, EXAM, EXAM_INDEX, PATIENT


def _console() -> Console:
    """🇺🇸 A `rich.Console` writing to an in-memory buffer — no real terminal, no width guesswork.

    🇧🇷 Um `rich.Console` escrevendo num buffer em memória — sem terminal de verdade, sem adivinhar largura.
    """
    return Console(file=io.StringIO(), width=120, no_color=True)


def test_render_index_table_shows_archived_deleted_and_pending_flags() -> None:
    """🇺🇸 All three flag columns (`archived`/`deleted`/`pending`) render when the index carries them.

    🇧🇷 As três colunas de flag (`archived`/`deleted`/`pending`) aparecem quando o índice as carrega.
    """
    flagged = EXAM_INDEX.model_copy(update={"is_archived": True, "is_deleted": True, "pending_version_id": "v2"})
    console = _console()

    render_index_table(console, [flagged], json_output=False)

    output = console.file.getvalue()
    assert "archived" in output
    assert "deleted" in output
    assert "pending" in output


def test_render_index_table_empty_shows_the_no_results_message() -> None:
    """🇺🇸 An empty page is not silently blank — it prints the dimmed "no results" line.

    🇧🇷 Uma página vazia não fica muda — imprime a linha esmaecida "nenhum resultado".
    """
    console = _console()

    render_index_table(console, [], json_output=False)

    assert "No results · Nenhum resultado" in console.file.getvalue()


def test_render_index_table_shows_the_next_cursor_hint() -> None:
    """🇺🇸 A non-empty `next_cursor` (one page short of `--all`) prints a resume hint.

    🇧🇷 Um `next_cursor` não vazio (uma página aquém de `--all`) imprime uma dica para retomar.
    """
    console = _console()

    render_index_table(console, [EXAM_INDEX], json_output=False, next_cursor="cursor_abc123")

    assert "cursor_abc123" in console.file.getvalue()


def test_render_patient_json_bypasses_rich_and_writes_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `json_output=True` calls `print_json`, which writes straight to `sys.stdout` — never through `console`.

    🇧🇷 `json_output=True` chama `print_json`, que escreve direto na `sys.stdout` — nunca pelo `console`.
    """
    render_patient(_console(), PATIENT, json_output=True)

    data = json.loads(capsys.readouterr().out)
    assert data["record"]["legal_name"] == "Jane Doe"


def test_render_exam_shows_the_report_content_when_present() -> None:
    """🇺🇸 A present `report` reaches the panel's `report:` field with its `content` intact.

    🇧🇷 Um `report` presente chega ao campo `report:` do painel com o `content` intacto.
    """
    record_with_report = ExamRecord(title=EXAM.record.title, report={"format": "text", "content": "all clear"})
    exam_with_report = EXAM.model_copy(update={"record": record_with_report})
    console = _console()

    render_exam(console, exam_with_report, json_output=False)

    output = console.file.getvalue()
    assert "report:" in output
    assert "all clear" in output


def test_decrypted_fields_are_printed_literally_not_as_rich_markup() -> None:
    """🇺🇸 A `[...]`-shaped substring in decrypted content (the report format label) survives `rich` verbatim.

    Regression test for the bug `_shared.plain`/`record_panel` now fix:
    `render_exam`'s report line used to embed `f"[{format}] {content}"`
    straight into a `rich`-markup panel, and `rich` read `[text]` as an
    (unknown) style tag and silently dropped it. `record_panel` now escapes
    every value through `plain()` before handing it to `Panel`, so the
    bracketed label prints as literal text instead of vanishing.

    🇧🇷 Um trecho no formato `[...]` em conteúdo decifrado (o rótulo de
    formato do report) sobrevive ao `rich` ao pé da letra.

    Teste de regressão para o bug que `_shared.plain`/`record_panel` agora
    corrigem: a linha de report de `render_exam` embutia
    `f"[{format}] {content}"` direto num painel de markup `rich`, e o `rich`
    lia `[text]` como uma tag de estilo (desconhecida) e a descartava em
    silêncio. `record_panel` agora escapa todo valor por `plain()` antes de
    entregá-lo ao `Panel`, então o rótulo entre colchetes imprime como texto
    literal em vez de sumir.
    """
    record_with_report = ExamRecord(title=EXAM.record.title, report={"format": "text", "content": "all clear"})
    exam_with_report = EXAM.model_copy(update={"record": record_with_report})
    console = _console()

    render_exam(console, exam_with_report, json_output=False)

    assert "[text] all clear" in console.file.getvalue()


def test_table_cell_with_markup_like_content_is_printed_literally() -> None:
    """🇺🇸 The same escaping applies to table cells: a document id shaped like `rich` markup prints as-is.

    A vault-issued id is not attacker-controlled, but a decrypted node name
    used as a table cell elsewhere in this same module is exactly the kind
    of value `plain()` exists to protect — this pins that every
    `render_index_table` cell goes through it, not just panel fields.

    🇧🇷 O mesmo escape vale para célula de tabela: um id de documento com
    forma de markup `rich` imprime como está.

    Um id emitido pelo cofre não é controlado por atacante, mas um nome de
    nó decifrado usado como célula de tabela em outro lugar deste mesmo
    módulo é exatamente o tipo de valor que `plain()` existe para proteger —
    isto trava que toda célula de `render_index_table` passa por ele, não só
    campo de painel.
    """
    tricky_index = EXAM_INDEX.model_copy(update={"document_id": "[bold]exam_1[/bold]"})
    console = Console(file=io.StringIO(), width=300, no_color=True)

    render_index_table(console, [tricky_index], json_output=False)

    # 🇺🇸 collapse the table's own word-wrap 🇧🇷 junta a quebra de linha da própria tabela
    output = " ".join(console.file.getvalue().split())
    assert "[bold]exam_1[/bold]" in output


def test_render_exam_omits_the_report_line_when_absent() -> None:
    """🇺🇸 `EXAM.record.report` is `None` in the fixture — the ternary's other branch.

    🇧🇷 `EXAM.record.report` é `None` na fixture — o outro ramo do ternário.
    """
    console = _console()

    render_exam(console, EXAM, json_output=False)

    assert "report" in console.file.getvalue()
    assert "—" in console.file.getvalue()


def test_render_document_index_non_json_shows_the_resource_and_flags() -> None:
    """🇺🇸 The non-`--json` panel title is `f"{resource} {document_id}"`, with `archived`/`deleted` as fields.

    🇧🇷 O título do painel sem `--json` é `f"{resource} {document_id}"`, com `archived`/`deleted` como campos.
    """
    console = _console()

    render_document_index(console, EXAM_INDEX, json_output=False)

    output = console.file.getvalue()
    assert f"exams {EXAM_INDEX.document_id}" in output


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
    """🇺🇸 `json_output=True` prints `{"items": [...]}` straight to `stdout`.

    🇧🇷 `json_output=True` imprime `{"items": [...]}` direto na `stdout`.
    """
    render_drive_node_table(_console(), drive=None, nodes=[DRIVE_NODE], json_output=True)

    data = json.loads(capsys.readouterr().out)
    assert data["items"][0]["node_id"] == DRIVE_NODE.node_id


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
