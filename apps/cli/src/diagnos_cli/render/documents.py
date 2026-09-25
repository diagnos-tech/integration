"""🇺🇸 Rendering for `patients`/`exams`: the index table, and the decrypted record panel.

By default the table (`render_index_table`) shows only `DocumentIndex`
fields — ids, dates, group, version counts — the same anonymous metadata the
vault itself can see. Names (or exam titles) appear only with `--summary`,
decrypted from each row's sealed `encrypted_index`; full content appears
only in the panel (`render_patient`/`render_exam`), because a caller asked
for one document with `get`. A terminal is a shared screen and a scrollback
buffer: clinical data is printed on request, never as a side effect.

🇧🇷 Renderização para `patients`/`exams`: a tabela do índice, e o painel do registro decifrado.

Por padrão a tabela (`render_index_table`) mostra só campos de
`DocumentIndex` — ids, datas, grupo, contagem de versões — o mesmo metadado
anônimo que o próprio cofre enxerga. Nomes (ou títulos de exame) só
aparecem com `--summary`, decifrados do `encrypted_index` selado de cada
linha; o conteúdo completo só aparece no painel (`render_patient`/
`render_exam`), porque quem chamou pediu um documento com `get`. Um
terminal é uma tela compartilhada e um histórico de rolagem: dado clínico é
impresso sob pedido, nunca como efeito colateral.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any

from rich.table import Table

from diagnos_cli.render._shared import plain, record_panel
from diagnos_cli.render.json import print_json

if TYPE_CHECKING:
    from collections.abc import Sequence

    from diagnos import DocumentIndex, DocumentListItem, Exam, Patient
    from diagnos.models import PatientAddress
    from rich.console import Console


def _summary_label(summary: Any) -> str | None:
    """🇺🇸 One line for a row's summary: a patient's name (+ tags) or an exam's title/modality/date.

    🇧🇷 Uma linha para o resumo de uma linha: o nome do paciente (+ tags) ou título/modalidade/data do exame.
    """
    if summary is None:
        return None
    data = summary.model_dump(exclude_none=True)
    if "display_name" in data or "legal_name" in data:
        name = str(data.get("display_name") or data.get("legal_name"))
        tags = data.get("tags") or []
        return f"{name} [{', '.join(tags)}]" if tags else name
    parts = [str(data[key]) for key in ("title", "modality", "exam_date") if data.get(key)]
    return " · ".join(parts) or None


def _flags(index: DocumentIndex) -> str:
    """🇺🇸 archived/deleted/pending/draft markers for one row. 🇧🇷 Marcas archived/deleted/pending/draft de uma linha."""
    flags = []
    if index.is_archived:
        flags.append("archived")
    if index.is_deleted:
        flags.append("deleted")
    if index.pending_version_id:
        flags.append("pending")
    if index.stream().draft_is_newer:
        flags.append("draft")
    return ", ".join(flags) or "—"


def render_index_table(
    console: Console,
    items: Sequence[DocumentListItem[Any]],
    *,
    json_output: bool,
    next_cursor: str | None = None,
    show_summary: bool = False,
) -> None:
    """🇺🇸 A table of patients or exams — anonymous metadata, plus the decrypted summary with `show_summary`.

    🇧🇷 Uma tabela de pacientes ou exames — metadado anônimo, mais o resumo decifrado com `show_summary`.
    """
    if json_output:
        # 🇺🇸 Same shape as the HTTP API's list (`{index, summary}`), `summary` null unless asked.
        # 🇧🇷 A mesma forma da lista da API HTTP (`{index, summary}`), `summary` nulo a menos que pedido.
        rows = [item if show_summary else item.model_copy(update={"summary": None}) for item in items]
        print_json({"items": rows, "next_cursor": next_cursor})
        return
    table = Table()
    table.add_column("ID")
    if show_summary:
        table.add_column("Summary · Resumo")
    table.add_column("Updated · Atualizado")
    table.add_column("Latest version · Última versão")
    table.add_column("Versions · Versões", justify="right")
    table.add_column("Group · Grupo")
    table.add_column("Flags")
    for item in items:
        index = item.index
        summary = [plain(_summary_label(item.summary))] if show_summary else []
        table.add_row(
            plain(index.document_id),
            *summary,
            plain(index.updated_at),
            plain(index.latest_version_id),
            str(len(index.versions)),
            plain(index.security_group_id),
            _flags(index),
        )
    console.print(table)
    if not items:
        console.print("[dim]No results · Nenhum resultado[/dim]")
    if next_cursor:
        console.print(f"[dim]next cursor · próximo cursor: {plain(next_cursor)}[/dim]")


def _source(document: Patient | Exam) -> str:
    """🇺🇸 Where the shown content came from: a committed version or the newer draft.

    🇧🇷 De onde veio o conteúdo mostrado: uma versão confirmada ou o rascunho mais novo.
    """
    if document.draft_rev is not None:
        return f"draft · rascunho (rev {document.draft_rev})"
    return f"version · versão {document.version_id}"


def _address(address: PatientAddress | None) -> str | None:
    """🇺🇸 A one-line address. 🇧🇷 Um endereço em uma linha."""
    if address is None:
        return None
    parts = [address.street, address.number, address.complement, address.district, address.city, address.state]
    line = ", ".join(part for part in parts if part)
    tail = " ".join(part for part in (address.postal_code, address.country) if part)
    return " — ".join(part for part in (line, tail) if part) or None


def render_patient(console: Console, patient: Patient, *, json_output: bool) -> None:
    """🇺🇸 The decrypted `PatientRecord`, in a panel — content only ever printed on explicit request (`get`).

    Identity documents are listed by name only: their values are sealed by
    the vault and opening one is an audited operation of the web app.

    🇧🇷 O `PatientRecord` decifrado, num painel — conteúdo só é impresso sob pedido explícito (`get`).

    Documentos de identidade aparecem só pelo nome: os valores são selados
    pelo cofre e abrir um é uma operação auditada do app web.
    """
    if json_output:
        print_json(patient)
        return
    record = patient.record
    identifiers = ", ".join(f"{item.name} (sealed · selado)" for item in record.identifiers or []) or None
    record_panel(
        console,
        f"Patient · Paciente {patient.id}",
        [
            ("legal_name", record.legal_name),
            ("display_name", record.display_name),
            ("external_id", record.external_id),
            ("identifiers", identifiers),
            ("birth_date", record.birth_date),
            ("biological_sex", record.biological_sex),
            ("gender_identity", record.gender_identity),
            ("race_identity", record.race_identity),
            ("email", record.email),
            ("phone", record.phone),
            ("address", _address(record.address)),
            ("tags", ", ".join(patient.tags) or None),
            ("source · origem", _source(patient)),
            ("updated_at", patient.updated_at),
            ("group · grupo", patient.security_group_id),
        ],
    )


class _TextOf(HTMLParser):
    """🇺🇸 Collects the text of an HTML report, one line per block.

    🇧🇷 Junta o texto de um laudo HTML, uma linha por bloco.
    """

    _BLOCKS = frozenset({"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"})

    def __init__(self) -> None:
        """🇺🇸 Starts empty. 🇧🇷 Começa vazio."""
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """🇺🇸 A block element starts a new line. 🇧🇷 Um elemento de bloco começa uma linha nova."""
        if tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """🇺🇸 Keeps the text as-is. 🇧🇷 Mantém o texto como veio."""
        self.parts.append(data)


def report_text(html: str | None) -> str | None:
    """🇺🇸 The plain text of `report_html` — never rendered as markup in a terminal.

    🇧🇷 O texto puro de `report_html` — nunca renderizado como marcação num terminal.
    """
    if not html:
        return None
    parser = _TextOf()
    parser.feed(html)
    parser.close()
    lines = [line.strip() for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line) or None


def render_exam(console: Console, exam: Exam, *, json_output: bool) -> None:
    """🇺🇸 The decrypted `ExamRecord`, in a panel — content only ever printed on explicit request (`get`).

    🇧🇷 O `ExamRecord` decifrado, num painel — conteúdo só é impresso sob pedido explícito (`get`).
    """
    if json_output:
        print_json(exam)
        return
    record = exam.record
    record_panel(
        console,
        f"Exam · Exame {exam.id}",
        [
            ("title", record.title),
            ("modality", record.modality),
            ("exam_date", record.exam_date),
            ("patient_id", exam.patient_id),
            ("report_status", exam.report_status),
            ("report", report_text(record.report_html)),
            ("source · origem", _source(exam)),
            ("updated_at", exam.updated_at),
            ("group · grupo", exam.security_group_id),
        ],
    )


def render_document_index(console: Console, index: DocumentIndex, *, json_output: bool) -> None:
    """🇺🇸 The result of a flag change (`archive`/`delete`/…) — index only, never re-fetches content.

    🇧🇷 O resultado de uma troca de flag (`archive`/`delete`/…) — só índice, nunca busca o conteúdo de novo.
    """
    if json_output:
        print_json(index)
        return
    record_panel(
        console,
        f"{index.resource} {index.document_id}",
        [
            ("updated_at", index.updated_at),
            ("latest_version_id", index.latest_version_id),
            ("group · grupo", index.security_group_id),
            ("archived", index.is_archived),
            ("deleted", index.is_deleted),
        ],
    )
