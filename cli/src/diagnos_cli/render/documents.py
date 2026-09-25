"""🇺🇸 Rendering for `patients`/`exams`: the anonymous index table, and the decrypted record panel.

The table (`render_index_table`) only ever shows `DocumentIndex` fields —
ids, dates, groups, version counts — the same anonymous metadata the vault
itself can see. The panel (`render_patient`/`render_exam`) is where
decrypted content appears, and only because a caller explicitly asked for
one document with `get` — never as a side effect of listing.

🇧🇷 Renderização para `patients`/`exams`: a tabela anônima do índice, e o
painel do registro decifrado.

A tabela (`render_index_table`) só mostra campos de `DocumentIndex` — ids,
datas, grupos, contagem de versões — o mesmo metadado anônimo que o próprio
cofre enxerga. O painel (`render_patient`/`render_exam`) é onde conteúdo
decifrado aparece, e só porque quem chamou pediu explicitamente um
documento com `get` — nunca como efeito colateral de uma listagem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from diagnos_cli.render._shared import plain, record_panel
from diagnos_cli.render.json import print_json

if TYPE_CHECKING:
    from diagnos import DocumentIndex, Exam, Patient
    from rich.console import Console


def render_index_table(
    console: Console,
    items: list[DocumentIndex],
    *,
    json_output: bool,
    next_cursor: str | None = None,
) -> None:
    """🇺🇸 A table of `DocumentIndex` (patients or exams) — anonymous metadata only, never decrypted content.

    🇧🇷 Uma tabela de `DocumentIndex` (pacientes ou exames) — só metadado anônimo, nunca conteúdo decifrado.
    """
    if json_output:
        print_json({"items": items, "next_cursor": next_cursor})
        return
    table = Table()
    table.add_column("ID")
    table.add_column("Updated · Atualizado")
    table.add_column("Latest version · Última versão")
    table.add_column("Versions · Versões", justify="right")
    table.add_column("Groups · Grupos")
    table.add_column("Flags")
    for index in items:
        flags = []
        if index.is_archived:
            flags.append("archived")
        if index.is_deleted:
            flags.append("deleted")
        if index.pending_version_id:
            flags.append("pending")
        table.add_row(
            plain(index.document_id),
            plain(index.updated_at),
            plain(index.latest_version_id),
            str(len(index.versions)),
            plain(", ".join(index.security_groups) or None),
            ", ".join(flags) or "—",
        )
    console.print(table)
    if not items:
        console.print("[dim]No results · Nenhum resultado[/dim]")
    if next_cursor:
        console.print(f"[dim]next cursor · próximo cursor: {plain(next_cursor)}[/dim]")


def render_patient(console: Console, patient: Patient, *, json_output: bool) -> None:
    """🇺🇸 The decrypted `PatientRecord`, in a panel — content only ever printed on explicit request (`get`).

    🇧🇷 O `PatientRecord` decifrado, num painel — conteúdo só é impresso sob pedido explícito (`get`).
    """
    if json_output:
        print_json(patient)
        return
    record = patient.record
    record_panel(
        console,
        f"Patient · Paciente {patient.id}",
        [
            ("legal_name", record.legal_name),
            ("display_name", record.display_name),
            ("legal_id", record.legal_id),
            ("external_id", record.external_id),
            ("birth_date", record.birth_date),
            ("biological_sex", record.biological_sex),
            ("gender_identity", record.gender_identity),
            ("email", record.email),
            ("phone", record.phone),
            ("updated_at", patient.updated_at),
            ("groups · grupos", ", ".join(patient.security_groups)),
        ],
    )


def render_exam(console: Console, exam: Exam, *, json_output: bool) -> None:
    """🇺🇸 The decrypted `ExamRecord`, in a panel — content only ever printed on explicit request (`get`).

    🇧🇷 O `ExamRecord` decifrado, num painel — conteúdo só é impresso sob pedido explícito (`get`).
    """
    if json_output:
        print_json(exam)
        return
    record = exam.record
    report = f"[{record.report.format}] {record.report.content}" if record.report else None
    record_panel(
        console,
        f"Exam · Exame {exam.id}",
        [
            ("title", record.title),
            ("description", record.description),
            ("patient_id", exam.patient_id),
            ("report", report),
            ("updated_at", exam.updated_at),
            ("groups · grupos", ", ".join(exam.security_groups)),
        ],
    )


def render_document_index(console: Console, index: DocumentIndex, *, json_output: bool) -> None:
    """🇺🇸 The result of a mutation (`create`/`update`/`archive`/…) — index only, never re-fetches content.

    🇧🇷 O resultado de uma mutação (`create`/`update`/`archive`/…) — só índice, nunca busca o conteúdo de novo.
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
            ("groups · grupos", ", ".join(index.security_groups)),
            ("archived", index.is_archived),
            ("deleted", index.is_deleted),
        ],
    )
