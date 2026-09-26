"""🇺🇸 `diagnos exams` — list, get, create, update, archive/unarchive, delete/restore.

🇧🇷 `diagnos exams` — listar, ler, criar, atualizar, arquivar/desarquivar, apagar/restaurar.
"""

from __future__ import annotations

from pathlib import Path

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.examples import examples
from diagnos_cli.inputs import load_record
from diagnos_cli.render import get_console, get_err_console, render_document_index, render_exam, render_index_table

app = typer.Typer(help="Exams · Exames")

_SUMMARY_HELP = (
    "Also decrypt each row's sealed summary (title, modality, date) · Também decifra o resumo selado de cada linha"
)
_ID_HELP = "Exam document id · Id do documento de exame"
_EXPECT_HELP = (
    "Refuse if a version newer than this one was saved meanwhile · Recusa se uma versão mais nova que esta foi salva"
)


@app.command(
    "list",
    help="List exams (one page, or all with --all) · Lista exames (uma página, ou todas com --all)",
    epilog=examples(
        (
            "diagnos exams list --group sg_radiology --summary",
            "One page, titles, modalities and dates decrypted · Uma página, títulos, modalidades e datas decifrados",
        ),
        ("diagnos --json exams list --all", "Every page, as JSON · Todas as páginas, em JSON"),
    ),
)
def list_exams(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group", "-g", help="Security group filter · Filtro de security group"),
    include_deleted: bool = typer.Option(False, "--include-deleted", help="Include the trash · Inclui a lixeira"),
    limit: int = typer.Option(50, "--limit", help="Page size · Tamanho da página"),
    cursor: str | None = typer.Option(None, "--cursor", help="Resume from this cursor · Retoma a partir deste cursor"),
    all_pages: bool = typer.Option(False, "--all", help="Walk every page · Percorre todas as páginas"),
    summary: bool = typer.Option(False, "--summary", "-s", help=_SUMMARY_HELP),
) -> None:
    """🇺🇸 One page of exams, or every page with `--all`; titles only with `--summary`.

    🇧🇷 Uma página de exames, ou todas com `--all`; títulos só com `--summary`.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        if all_pages:
            items = list(vault.exams.iter_all(security_group=group, include_deleted=include_deleted, limit=limit))
            next_cursor = None
        else:
            page = vault.exams.list(security_group=group, include_deleted=include_deleted, limit=limit, cursor=cursor)
            items, next_cursor = list(page.items), page.next_cursor
    render_index_table(console, items, json_output=opts.json_output, next_cursor=next_cursor, show_summary=summary)


@app.command(
    "get",
    help="Fetch and decrypt one exam · Busca e decifra um exame",
    epilog=examples(
        ("diagnos exams get EXAM_ID", "The exam, its report as plain text · O exame, com o laudo em texto puro"),
        (
            "diagnos --json exams get EXAM_ID",
            "The full record, report HTML included · O registro completo, com o HTML do laudo",
        ),
    ),
)
def get_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(..., help=_ID_HELP),
    version: str | None = typer.Option(None, "--version", help="A specific version id · Um id de versão específico"),
    committed: bool = typer.Option(
        False, "--committed", help="Ignore a newer unsaved draft · Ignora um rascunho mais novo não salvo"
    ),
) -> None:
    """🇺🇸 Fetches and decrypts one exam — the only place exam content is ever printed.

    🇧🇷 Busca e decifra um exame — o único lugar onde o conteúdo do exame é impresso.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        exam = vault.exams.get(exam_id, version_id=version, include_draft=not committed)
    render_exam(console, exam, json_output=opts.json_output)


@app.command(
    "create",
    help="Encrypt and create an exam for a patient · Cifra e cria um exame de um paciente",
    epilog=examples(
        (
            "diagnos exams create --patient PATIENT_ID --group sg_radiology"
            ' --title "Chest CT" --modality CT --exam-date 2026-09-01',
            "Inline fields; only the patient id travels in clear · Campos inline; só o id do paciente vai em claro",
        ),
        (
            "diagnos exams create --patient PATIENT_ID --group sg_radiology --file exam.json",
            "With the report, from a JSON file · Com o laudo, de um arquivo JSON",
        ),
    ),
)
def create_exam(
    ctx: typer.Context,
    patient_id: str = typer.Option(..., "--patient", help="The exam's patient id · Id do paciente do exame"),
    group: str = typer.Option(..., "--group", "-g", help="Security group to encrypt under · Grupo sob o qual cifrar"),
    file: Path | None = typer.Option(None, "--file", help="Record JSON file · Arquivo JSON do registro"),
    title: str | None = typer.Option(None, "--title", help="e.g. Chest CT · ex: TC de tórax"),
    modality: str | None = typer.Option(None, "--modality", help="e.g. CT, MR, US · ex: CT, MR, US"),
    exam_date: str | None = typer.Option(None, "--exam-date", help="ISO date · Data ISO"),
) -> None:
    """🇺🇸 Encrypts a new exam under `--group`; only `--patient` goes to clear `meta`, the rest is sealed.

    🇧🇷 Cifra um exame novo sob `--group`; só `--patient` vai ao `meta` em claro, o resto é selado.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {"title": title, "modality": modality, "exam_date": exam_date})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        exam = vault.exams.create(record, patient_id=patient_id, security_group=group)
    render_exam(console, exam, json_output=opts.json_output)


@app.command(
    "update",
    help="Write a new version of an exam · Grava uma versão nova de um exame",
    epilog=examples(
        (
            "diagnos exams update EXAM_ID --file exam.json --expect-version VERSION_ID",
            "A complete new version, refused if someone saved since"
            " · Uma versão completa nova, recusada se alguém salvou depois",
        )
    ),
)
def update_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(..., help=_ID_HELP),
    file: Path = typer.Option(..., "--file", help="New record JSON file · Arquivo JSON do registro novo"),
    expect_version: str | None = typer.Option(None, "--expect-version", help=_EXPECT_HELP),
) -> None:
    """🇺🇸 Encrypts a brand new, complete version of the record, reusing the exam's existing DEK.

    🇧🇷 Cifra uma versão nova e completa do registro, reusando a DEK existente do exame.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        exam = vault.exams.update(exam_id, record, expected_latest_version_id=expect_version)
    render_exam(console, exam, json_output=opts.json_output)


@app.command(
    "archive",
    help="Archive an exam · Arquiva um exame",
    epilog=examples(
        (
            "diagnos exams archive EXAM_ID",
            "Set the archived flag; no new version · Liga a flag de arquivado; sem versão nova",
        )
    ),
)
def archive_exam(ctx: typer.Context, exam_id: str = typer.Argument(..., help=_ID_HELP)) -> None:
    """🇺🇸 Marks the exam archived (a flag, no new version). 🇧🇷 Marca o exame arquivado (uma flag, sem versão nova)."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.archive(exam_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command(
    "unarchive",
    help="Unarchive an exam · Desarquiva um exame",
    epilog=examples(("diagnos exams unarchive EXAM_ID", "Clear the archived flag · Tira a flag de arquivado")),
)
def unarchive_exam(ctx: typer.Context, exam_id: str = typer.Argument(..., help=_ID_HELP)) -> None:
    """🇺🇸 Clears the archived flag. 🇧🇷 Tira a flag de arquivado."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.unarchive(exam_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command(
    "delete",
    help="Move an exam to the trash · Manda um exame para a lixeira",
    epilog=examples(
        (
            "diagnos exams delete EXAM_ID --yes",
            "Move to the trash without the prompt · Manda para a lixeira sem a pergunta",
        )
    ),
)
def delete_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(..., help=_ID_HELP),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt · Pula a confirmação"),
) -> None:
    """🇺🇸 Flags the exam deleted — never a hard delete; `restore` undoes it.

    🇧🇷 Marca o exame como apagado — nunca um apagar de verdade; `restore` desfaz.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    if not yes:
        confirmed = typer.confirm(f"Move exam {exam_id} to the trash? · Mandar o exame {exam_id} à lixeira?")
        if not confirmed:
            raise typer.Exit(code=0)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.delete(exam_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command(
    "restore",
    help="Take an exam out of the trash · Tira um exame da lixeira",
    epilog=examples(
        (
            "diagnos exams restore EXAM_ID",
            "Back out of the trash, history intact · De volta da lixeira, histórico intacto",
        )
    ),
)
def restore_exam(ctx: typer.Context, exam_id: str = typer.Argument(..., help=_ID_HELP)) -> None:
    """🇺🇸 Clears the deleted flag. 🇧🇷 Tira a flag de apagado."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.restore(exam_id)
    render_document_index(console, index, json_output=opts.json_output)
