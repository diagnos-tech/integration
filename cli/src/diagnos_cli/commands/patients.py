"""🇺🇸 `diagnos patients` — list, get, create, update, archive/unarchive/delete.

🇧🇷 `diagnos patients` — listar, ler, criar, atualizar, arquivar/desarquivar/apagar.
"""

from __future__ import annotations

from pathlib import Path

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.inputs import load_record
from diagnos_cli.render import get_console, get_err_console, render_document_index, render_index_table, render_patient

app = typer.Typer(help="Patients · Pacientes")


@app.command("list")
def list_patients(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group", "-g", help="Security group filter · Filtro de security group"),
    include_deleted: bool = typer.Option(False, "--include-deleted", help="Include soft-deleted · Inclui apagados"),
    limit: int = typer.Option(50, "--limit", help="Page size · Tamanho da página"),
    cursor: str | None = typer.Option(None, "--cursor", help="Resume from this cursor · Retoma a partir deste cursor"),
    all_pages: bool = typer.Option(False, "--all", help="Walk every page · Percorre todas as páginas"),
) -> None:
    """🇺🇸 One page of patient indexes, or every page with `--all`.

    🇧🇷 Uma página de índices de paciente, ou todas as páginas com `--all`.
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
    render_index_table(console, items, json_output=opts.json_output, next_cursor=next_cursor)


@app.command("get")
def get_patient(
    ctx: typer.Context,
    patient_id: str = typer.Argument(..., help="Patient document id · Id do documento de paciente"),
    version: str | None = typer.Option(None, "--version", help="A specific version id · Um id de versão específico"),
) -> None:
    """🇺🇸 Fetches and decrypts one patient — the only place patient content is ever printed.

    🇧🇷 Busca e decifra um paciente — o único lugar onde o conteúdo do paciente é impresso.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        patient = vault.patients.get(patient_id, version_id=version)
    render_patient(console, patient, json_output=opts.json_output)


@app.command("create")
def create_patient(
    ctx: typer.Context,
    group: str = typer.Option(..., "--group", "-g", help="Security group to encrypt under · Grupo sob o qual cifrar"),
    file: Path | None = typer.Option(None, "--file", help="Record JSON file · Arquivo JSON do registro"),
    legal_name: str | None = typer.Option(None, "--legal-name"),
    display_name: str | None = typer.Option(None, "--display-name"),
    birth_date: str | None = typer.Option(None, "--birth-date", help="ISO date, e.g. 1990-01-31 · Data ISO"),
) -> None:
    """🇺🇸 Encrypts a new patient under `--group`, from `--file` or the inline flags.

    `birth_date` stays a plain `str` here — `typer`/`click` have no built-in
    type for `datetime.date` (only `datetime.datetime`), and `PatientRecord`
    (`sdk/src/diagnos/models.py`) already validates an ISO `"YYYY-MM-DD"`
    string into a real `date` itself, so parsing it twice would just be
    duplicated, driftable validation.

    🇧🇷 Cifra um paciente novo sob `--group`, a partir de `--file` ou das flags inline.

    `birth_date` fica como `str` puro aqui — `typer`/`click` não têm tipo
    embutido para `datetime.date` (só para `datetime.datetime`), e o
    `PatientRecord` (`sdk/src/diagnos/models.py`) já valida uma string ISO
    `"YYYY-MM-DD"` numa `date` de verdade sozinho, então validar duas vezes
    seria só validação duplicada e sujeita a divergir.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {"legal_name": legal_name, "display_name": display_name, "birth_date": birth_date})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        patient = vault.patients.create(record, security_group=group)
    render_patient(console, patient, json_output=opts.json_output)


@app.command("update")
def update_patient(
    ctx: typer.Context,
    patient_id: str = typer.Argument(...),
    file: Path = typer.Option(..., "--file", help="New record JSON file · Arquivo JSON do registro novo"),
) -> None:
    """🇺🇸 Encrypts a brand new version of the record, reusing the patient's existing DEK.

    🇧🇷 Cifra uma versão nova do registro, reusando a DEK existente do paciente.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    record = load_record(file, {})
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        patient = vault.patients.update(patient_id, record)
    render_patient(console, patient, json_output=opts.json_output)


@app.command("archive")
def archive_patient(ctx: typer.Context, patient_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Marks the patient archived, in a new version. 🇧🇷 Marca o paciente arquivado, numa versão nova."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.patients.archive(patient_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("unarchive")
def unarchive_patient(ctx: typer.Context, patient_id: str = typer.Argument(...)) -> None:
    """🇺🇸 Clears the archived flag, in a new version. 🇧🇷 Tira a flag de arquivado, numa versão nova."""
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.patients.unarchive(patient_id)
    render_document_index(console, index, json_output=opts.json_output)


@app.command("delete")
def delete_patient(
    ctx: typer.Context,
    patient_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt · Pula a confirmação"),
) -> None:
    """🇺🇸 Flags the index deleted, in a new version — the encrypted history stays (`sdk/README.md`).

    🇧🇷 Marca o índice como apagado, numa versão nova — o histórico cifrado permanece (`sdk/README.md`).
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    if not yes:
        confirmed = typer.confirm(f"Delete patient {patient_id}? · Apagar paciente {patient_id}?")
        if not confirmed:
            raise typer.Exit(code=0)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        index = vault.patients.delete(patient_id)
    render_document_index(console, index, json_output=opts.json_output)
