"""🇺🇸 `diagnos patients` — list, get, create, update, archive/unarchive, delete/restore.

🇧🇷 `diagnos patients` — listar, ler, criar, atualizar, arquivar/desarquivar, apagar/restaurar.
"""

from __future__ import annotations

from pathlib import Path

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.inputs import load_record
from diagnos_cli.render import get_console, get_err_console, render_document_index, render_index_table, render_patient

app = typer.Typer(help="Patients · Pacientes")

_SUMMARY_HELP = (
    "Also decrypt each row's sealed summary (name, tags) · Também decifra o resumo selado de cada linha (nome, tags)"
)
_EXPECT_HELP = (
    "Refuse if a version newer than this one was saved meanwhile · Recusa se uma versão mais nova que esta foi salva"
)


@app.command(
    "list", help="List patients (one page, or all with --all) · Lista pacientes (uma página, ou todas com --all)"
)
def list_patients(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group", "-g", help="Security group filter · Filtro de security group"),
    include_deleted: bool = typer.Option(False, "--include-deleted", help="Include the trash · Inclui a lixeira"),
    limit: int = typer.Option(50, "--limit", help="Page size · Tamanho da página"),
    cursor: str | None = typer.Option(None, "--cursor", help="Resume from this cursor · Retoma a partir deste cursor"),
    all_pages: bool = typer.Option(False, "--all", help="Walk every page · Percorre todas as páginas"),
    summary: bool = typer.Option(False, "--summary", "-s", help=_SUMMARY_HELP),
) -> None:
    """🇺🇸 One page of patients, or every page with `--all`; names only with `--summary`.

    🇧🇷 Uma página de pacientes, ou todas com `--all`; nomes só com `--summary`.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        if all_pages:
            items = list(vault.patients.iter_all(security_group=group, include_deleted=include_deleted, limit=limit))
            next_cursor = None
        else:
            page = vault.patients.list(
                security_group=group, include_deleted=include_deleted, limit=limit, cursor=cursor
            )
            items, next_cursor = list(page.items), page.next_cursor
    render_index_table(console, items, json_output=opts.json_output, next_cursor=next_cursor, show_summary=summary)


@app.command("get", help="Fetch and decrypt one patient · Busca e decifra um paciente")
def get_patient(
    ctx: typer.Context,
    patient_id: str = typer.Argument(..., help="Patient document id · Id do documento de paciente"),
    version: str | None = typer.Option(None, "--version", help="A specific version id · Um id de versão específico"),
    committed: bool = typer.Option(
        False, "--committed", help="Ignore a newer unsaved draft · Ignora um rascunho mais novo não salvo"
    ),
) -> None:
    """🇺🇸 Fetches and decrypts one patient — the only place patient content is ever printed.

    Like the web app, the newest content wins: the editor's draft when it
    is newer than the latest version. `--committed` reads saved versions only.

    🇧🇷 Busca e decifra um paciente — o único lugar onde o conteúdo do paciente é impresso.

    Como no app web, o conteúdo mais novo vence: o rascunho do editor quando
    é mais novo que a versão corrente. `--committed` lê só versões salvas.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        patient = vault.patients.get(patient_id, version_id=version, include_draft=not committed)
    render_patient(console, patient, json_output=opts.json_output)


@app.command("create", help="Encrypt and create a patient · Cifra e cria um paciente")
def create_patient(
    ctx: typer.Context,
    group: str = typer.Option(..., "--group", "-g", help="Security group to encrypt under · Grupo sob o qual cifrar"),
    file: Path | None = typer.Option(None, "--file", help="Record JSON file · Arquivo JSON do registro"),
    legal_name: str | None = typer.Option(None, "--legal-name"),
    display_name: str | None = typer.Option(None, "--display-name"),
    birth_date: str | None = typer.Option(None, "--birth-date", help="ISO date, e.g. 1990-01-31 · Data ISO"),
    external_id: str | None = typer.Option(None, "--external-id", help="Id in another system · Id em outro sistema"),
    tags: list[str] | None = typer.Option(
        None, "--tag", help="Sealed list label, repeatable · Rótulo selado, repetível"
    ),
) -> None:
    """🇺🇸 Encrypts a new patient under `--group`, from `--file` or the inline flags.

    `birth_date` stays a plain `str` here: `PatientRecord` itself accepts an
    ISO date and stores it the way the web app does, so parsing it twice
    would be duplicated, driftable validation.

    🇧🇷 Cifra um paciente novo sob `--group`, a partir de `--file` ou das flags inline.

    `birth_date` fica como `str` puro aqui: o próprio `PatientRecord` aceita
    uma data ISO e a grava do jeito que o app web grava, então validar duas
    vezes seria validação duplicada e sujeita a divergir.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    inline = {
        "legal_name": legal_name,
        "display_name": display_name,
        "birth_date": birth_date,
        "external_id": external_id,
    }
    record = load_record(file, inline)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        patient = vault.patients.create(record, security_group=group, tags=tags or ())
    render_patient(console, patient, json_output=opts.json_output)


@app.command("update", help="Write a new version of a patient · Grava uma versão nova de um paciente")
def update_patient(
    ctx: typer.Context,
    patient_id: str = typer.Argument(...),
    file: Path = typer.Option(..., "--file", help="New record JSON file · Arquivo JSON do registro novo"),
    tags: list[str] | None = typer.Option(
        None, "--tag", help="Replace the tags, repeatable (default: keep) · Substitui as tags (padrão: mantém)"
    ),
    expect_version: str | None = typer.Option(None, "--expect-version", help=_EXPECT_HELP),
) -> None:
    """🇺🇸 Encrypts a brand new, complete version of the record, reusing the patient's existing DEK.

    🇧🇷 Cifra uma versão nova e completa do registro, reusando a DEK existente do paciente.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        patient = vault.patients.update(patient_id, record, tags=tags, expected_latest_version_id=expect_version)
    render_patient(console, patient, json_output=opts.json_output)


@app.command("archive", help="Archive a patient · Arquiva um paciente")
def archive_patient(ctx: typer.Context, patient_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Marks the patient archived (a flag, no new version).

    🇧🇷 Marca o paciente arquivado (uma flag, sem versão nova).
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.patients.archive(patient_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("unarchive", help="Unarchive a patient · Desarquiva um paciente")
def unarchive_patient(ctx: typer.Context, patient_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Clears the archived flag. 🇧🇷 Tira a flag de arquivado."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.patients.unarchive(patient_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("delete", help="Move a patient to the trash · Manda um paciente para a lixeira")
def delete_patient(
    ctx: typer.Context,
    patient_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt · Pula a confirmação"),
) -> None:
    """🇺🇸 Flags the patient deleted — never a hard delete; `restore` undoes it.

    🇧🇷 Marca o paciente como apagado — nunca um apagar de verdade; `restore` desfaz.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    if not yes:
        confirmed = typer.confirm(
            f"Move patient {patient_id} to the trash? · Mandar o paciente {patient_id} à lixeira?"
        )
        if not confirmed:
            raise typer.Exit(code=0)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.patients.delete(patient_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("restore", help="Take a patient out of the trash · Tira um paciente da lixeira")
def restore_patient(ctx: typer.Context, patient_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Clears the deleted flag. 🇧🇷 Tira a flag de apagado."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.patients.restore(patient_id)
    render_document_index(console, index, json_output=opts.json_output)
