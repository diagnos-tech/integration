"""🇺🇸 `diagnos exams` — list, get, create, update, archive/unarchive, delete/restore.

🇧🇷 `diagnos exams` — listar, ler, criar, atualizar, arquivar/desarquivar, apagar/restaurar.
"""

from __future__ import annotations

from pathlib import Path

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.group_choice import GROUP_ENV_VAR, resolve_group
from diagnos_cli.inputs import load_record
from diagnos_cli.render import get_console, get_err_console, render_document_index, render_exam, render_index_table

app = typer.Typer(help="Exams · Exames")

_SUMMARY_HELP = (
    "Also decrypt each row's sealed summary (title, modality, date) · Também decifra o resumo selado de cada linha"
)
_EXPECT_HELP = (
    "Refuse if a version newer than this one was saved meanwhile · Recusa se uma versão mais nova que esta foi salva"
)


@app.command("list", help="List exams (one page, or all with --all) · Lista exames (uma página, ou todas com --all)")
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


@app.command("get", help="Fetch and decrypt one exam · Busca e decifra um exame")
def get_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(..., help="Exam document id · Id do documento de exame"),
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


@app.command("create", help="Encrypt and create an exam for a patient · Cifra e cria um exame de um paciente")
def create_exam(
    ctx: typer.Context,
    patient_id: str = typer.Option(..., "--patient", help="The exam's patient id · Id do paciente do exame"),
    group: str | None = typer.Option(
        None,
        "--group",
        "-g",
        envvar=GROUP_ENV_VAR,
        show_envvar=True,
        help="Security group to seal under (default: the patient's) · Grupo sob o qual selar (padrão: o do paciente)",
    ),
    file: Path | None = typer.Option(
        None, "--file", help="Record JSON file, `-` for stdin · Arquivo JSON do registro, `-` para stdin"
    ),
    title: str | None = typer.Option(None, "--title"),
    modality: str | None = typer.Option(None, "--modality", help="e.g. CT, MR, US · ex: CT, MR, US"),
    exam_date: str | None = typer.Option(None, "--exam-date", help="ISO date · Data ISO"),
) -> None:
    """🇺🇸 Encrypts a new exam — by default in its patient's group; only `--patient` goes to clear `meta`.

    🇧🇷 Cifra um exame novo — por padrão no grupo do paciente; só `--patient` vai ao `meta` em claro.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {"title": title, "modality": modality, "exam_date": exam_date})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        inferred = (
            None if group else (vault.patients.index(patient_id).security_group_id, "the patient's · o do paciente")
        )
        group = resolve_group(vault, group, err_console=err_console, quiet=opts.quiet, inferred=inferred)
        exam = vault.exams.create(record, patient_id=patient_id, security_group=group)
    render_exam(console, exam, json_output=opts.json_output)


@app.command("update", help="Write a new version of an exam · Grava uma versão nova de um exame")
def update_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(...),
    file: Path = typer.Option(
        ..., "--file", help="New record JSON file, `-` for stdin · Arquivo JSON do registro novo, `-` para stdin"
    ),
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


@app.command("archive", help="Archive an exam · Arquiva um exame")
def archive_exam(ctx: typer.Context, exam_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Marks the exam archived (a flag, no new version). 🇧🇷 Marca o exame arquivado (uma flag, sem versão nova)."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.archive(exam_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("unarchive", help="Unarchive an exam · Desarquiva um exame")
def unarchive_exam(ctx: typer.Context, exam_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Clears the archived flag. 🇧🇷 Tira a flag de arquivado."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.unarchive(exam_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("delete", help="Move an exam to the trash · Manda um exame para a lixeira")
def delete_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(...),
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


@app.command("restore", help="Take an exam out of the trash · Tira um exame da lixeira")
def restore_exam(ctx: typer.Context, exam_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Clears the deleted flag. 🇧🇷 Tira a flag de apagado."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.restore(exam_id)
    render_document_index(console, index, json_output=opts.json_output)
