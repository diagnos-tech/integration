"""🇺🇸 `diagnos exams` — list, get, create, update, archive/unarchive/delete.

🇧🇷 `diagnos exams` — listar, ler, criar, atualizar, arquivar/desarquivar/apagar.
"""

from __future__ import annotations

from pathlib import Path

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.inputs import load_record
from diagnos_cli.render import get_console, get_err_console, render_document_index, render_exam, render_index_table

app = typer.Typer(help="Exams · Exames")


@app.command("list", help="List exams (one page, or all with --all) · Lista exames (uma página, ou todas com --all)")
def list_exams(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group", "-g", help="Security group filter · Filtro de security group"),
    include_deleted: bool = typer.Option(False, "--include-deleted", help="Include soft-deleted · Inclui apagados"),
    limit: int = typer.Option(50, "--limit", help="Page size · Tamanho da página"),
    cursor: str | None = typer.Option(None, "--cursor", help="Resume from this cursor · Retoma a partir deste cursor"),
    all_pages: bool = typer.Option(False, "--all", help="Walk every page · Percorre todas as páginas"),
) -> None:
    """🇺🇸 One page of exam indexes, or every page with `--all`.

    🇧🇷 Uma página de índices de exame, ou todas as páginas com `--all`.
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
    render_index_table(console, items, json_output=opts.json_output, next_cursor=next_cursor)


@app.command("get", help="Fetch and decrypt one exam · Busca e decifra um exame")
def get_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(..., help="Exam document id · Id do documento de exame"),
    version: str | None = typer.Option(None, "--version", help="A specific version id · Um id de versão específico"),
) -> None:
    """🇺🇸 Fetches and decrypts one exam — the only place exam content is ever printed.

    🇧🇷 Busca e decifra um exame — o único lugar onde o conteúdo do exame é impresso.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        exam = vault.exams.get(exam_id, version_id=version)
    render_exam(console, exam, json_output=opts.json_output)


@app.command("create", help="Encrypt and create an exam for a patient · Cifra e cria um exame de um paciente")
def create_exam(
    ctx: typer.Context,
    patient_id: str = typer.Option(..., "--patient", help="Owning patient id · Id do paciente dono"),
    group: str = typer.Option(..., "--group", "-g", help="Security group to encrypt under · Grupo sob o qual cifrar"),
    modality: str | None = typer.Option(None, "--modality", help="e.g. CT, MRI · ex: CT, RM"),
    file: Path | None = typer.Option(None, "--file", help="Record JSON file · Arquivo JSON do registro"),
    title: str | None = typer.Option(None, "--title"),
) -> None:
    """🇺🇸 Encrypts a new exam under `--group`, linked to `--patient` in clear `meta`.

    🇧🇷 Cifra um exame novo sob `--group`, ligado a `--patient` no `meta` em claro.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {"title": title})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        exam = vault.exams.create(record, patient_id=patient_id, security_group=group, modality=modality)
    render_exam(console, exam, json_output=opts.json_output)


@app.command("update", help="Write a new version of an exam · Grava uma versão nova de um exame")
def update_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(...),
    file: Path = typer.Option(..., "--file", help="New record JSON file · Arquivo JSON do registro novo"),
    modality: str | None = typer.Option(None, "--modality"),
) -> None:
    """🇺🇸 Encrypts a brand new version of the record, reusing the exam's existing DEK.

    🇧🇷 Cifra uma versão nova do registro, reusando a DEK existente do exame.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        exam = vault.exams.update(exam_id, record, modality=modality)
    render_exam(console, exam, json_output=opts.json_output)


@app.command("archive", help="Archive an exam (new version) · Arquiva um exame (versão nova)")
def archive_exam(ctx: typer.Context, exam_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Marks the exam archived, in a new version. 🇧🇷 Marca o exame arquivado, numa versão nova."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.archive(exam_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("unarchive", help="Unarchive an exam (new version) · Desarquiva um exame (versão nova)")
def unarchive_exam(ctx: typer.Context, exam_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Clears the archived flag, in a new version. 🇧🇷 Tira a flag de arquivado, numa versão nova."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.unarchive(exam_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("delete", help="Flag an exam as deleted (new version) · Marca um exame como apagado (versão nova)")
def delete_exam(
    ctx: typer.Context,
    exam_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt · Pula a confirmação"),
) -> None:
    """🇺🇸 Flags the index deleted, in a new version — the encrypted history stays (`sdk/README.md`).

    🇧🇷 Marca o índice como apagado, numa versão nova — o histórico cifrado permanece (`sdk/README.md`).
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    if not yes:
        confirmed = typer.confirm(f"Delete exam {exam_id}? · Apagar exame {exam_id}?")
        if not confirmed:
            raise typer.Exit(code=0)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.exams.delete(exam_id)
    render_document_index(console, index, json_output=opts.json_output)
