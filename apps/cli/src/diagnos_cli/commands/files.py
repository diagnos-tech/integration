"""🇺🇸 `diagnos files` — list, upload, download, get, against one security group's drive.

`upload`/`upload_many`/`download` (`apps/sdk/src/diagnos/resources/drives/`)
have no progress-callback hook: they are one blocking call that returns
only once every byte has moved. So the progress bar below can show one row
per file and *that a batch is in flight*, but not real byte-level progress
per file — flagged as an SDK gap (a progress callback would let the CLI
drive per-file percentages honestly) rather than faked with a fixed
animation.

🇧🇷 `diagnos files` — listar, subir, baixar, ler, contra o drive de um
security group.

`upload`/`upload_many`/`download`
(`apps/sdk/src/diagnos/resources/drives/`) não têm gancho de callback de
progresso: são uma única chamada bloqueante que só volta quando todo byte já
se moveu. Então a barra de progresso abaixo consegue mostrar uma linha por
arquivo e *que um lote está em voo*, mas não progresso real por byte por
arquivo — sinalizado como lacuna do SDK (um callback de progresso deixaria a
CLI mostrar porcentagem por arquivo com honestidade) em vez de simulado com
uma animação fixa.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import typer
from diagnos import DriveNode
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.render import get_console, get_err_console, print_json, render_drive_node, render_drive_node_table

# 🇺🇸 `vault.drives.drive(...)` returns an `diagnos.resources.drives.Drive`,
# not re-exported from top-level `diagnos` (SDK gap, reported separately);
# `Any` stands in so this module still imports only `diagnos` itself.
# 🇧🇷 `vault.drives.drive(...)` devolve uma `diagnos.resources.drives.Drive`,
# não reexportada por `diagnos` no topo (lacuna do SDK, relatada à parte);
# `Any` substitui para este módulo continuar importando só `diagnos`.
Drive = Any

app = typer.Typer(help="Drive files · Arquivos de drive")


@app.command(
    "list",
    help="List a drive's files (one page, or all with --all) · Lista arquivos do drive (uma página, ou --all)",
)
def list_files(
    ctx: typer.Context,
    group: str = typer.Option(..., "--group", "-g", help="Security group (drive) · Security group (drive)"),
    exam: str | None = typer.Option(None, "--exam", help="Filter by exam id · Filtra por id de exame"),
    include_pending: bool = typer.Option(False, "--include-pending", help="Include pending · Inclui pendentes"),
    limit: int = typer.Option(50, "--limit", help="Page size · Tamanho da página"),
    cursor: str | None = typer.Option(None, "--cursor", help="Resume from this cursor · Retoma a partir deste cursor"),
    all_pages: bool = typer.Option(False, "--all", help="Walk every page · Percorre todas as páginas"),
) -> None:
    """🇺🇸 One page of drive nodes, or every page with `--all`.

    🇧🇷 Uma página de nós de drive, ou todas as páginas com `--all`.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        drive = vault.drives.drive(group)
        if all_pages:
            nodes = list(drive.iter_all(exam_id=exam, include_pending=include_pending, limit=limit))
        else:
            page = drive.list(exam_id=exam, include_pending=include_pending, limit=limit, cursor=cursor)
            nodes = list(page.items)
    render_drive_node_table(console, drive, nodes, json_output=opts.json_output)


def _upload_with_progress(
    console: Console, drive: Drive, paths: list[Path], *, exam_id: str | None, quiet: bool
) -> list[DriveNode]:
    """🇺🇸 One progress row per file; every row completes together, since `upload_many` is one blocking call.

    🇧🇷 Uma linha de progresso por arquivo; toda linha completa junto, já
    que `upload_many` é uma única chamada bloqueante.
    """
    # 🇺🇸 `cast`, not a real check: `drive` is typed `Any` (the `Drive`
    # export gap above), so mypy strict sees `upload_many`'s return as `Any`
    # and would otherwise flag "returning Any" here on a function that
    # promises `list[DriveNode]`.
    # 🇧🇷 `cast`, não uma checagem de verdade: `drive` é tipado `Any` (a
    # lacuna de exportar `Drive` acima), então o mypy strict vê o retorno de
    # `upload_many` como `Any` e sinalizaria "retornando Any" aqui numa
    # função que promete `list[DriveNode]`.
    if quiet:
        return cast("list[DriveNode]", drive.upload_many([str(path) for path in paths], exam_id=exam_id))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        tasks = [progress.add_task(path.name, total=1) for path in paths]
        nodes = cast("list[DriveNode]", drive.upload_many([str(path) for path in paths], exam_id=exam_id))
        for task_id in tasks:
            progress.update(task_id, completed=1)
    return nodes


@app.command("upload", help="Encrypt and upload files · Cifra e envia arquivos")
def upload_files(
    ctx: typer.Context,
    paths: list[Path] = typer.Argument(..., help="Files to upload · Arquivos para subir"),
    group: str = typer.Option(..., "--group", "-g", help="Security group (drive) · Security group (drive)"),
    exam: str | None = typer.Option(None, "--exam", help="Attach to this exam id · Vincula a este id de exame"),
) -> None:
    """🇺🇸 Uploads every path in one batch (`Drive.upload_many`), single vs. multipart decided per file by the SDK.

    🇧🇷 Sobe todo path num único lote (`Drive.upload_many`), single ou multipart decidido por arquivo pelo SDK.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise typer.BadParameter(f"not a file · não é um arquivo: {missing[0]}")
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        drive = vault.drives.drive(group)
        nodes = _upload_with_progress(err_console, drive, paths, exam_id=exam, quiet=opts.quiet)
    render_drive_node_table(console, drive, nodes, json_output=opts.json_output)


@app.command("download", help="Download and decrypt one file · Baixa e decifra um arquivo")
def download_file(
    ctx: typer.Context,
    node_id: str = typer.Argument(...),
    group: str = typer.Option(..., "--group", "-g", help="Security group (drive) · Security group (drive)"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination path (default: the decrypted name) · Caminho de destino (padrão: o nome decifrado)",
    ),
) -> None:
    """🇺🇸 Downloads and decrypts one node, straight to `--output` or to its decrypted name.

    🇧🇷 Baixa e decifra um nó, direto para `--output` ou para o nome decifrado dele.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        drive = vault.drives.drive(group)
        destination = output if output is not None else Path(drive.name_of(drive.get(node_id)) or node_id)
        status = None if opts.quiet else err_console.status("[cyan]downloading… · baixando…[/cyan]", spinner="dots")
        if status is not None:
            status.start()
        try:
            drive.download(node_id, destination)
        finally:
            if status is not None:
                status.stop()

    if opts.json_output:
        print_json({"node_id": node_id, "saved_to": str(destination)})
    elif not opts.quiet:
        console.print(f"[green]Saved · Salvo:[/green] {destination}")


@app.command("get", help="Show one file's metadata and name · Mostra metadados e nome de um arquivo")
def get_file(
    ctx: typer.Context,
    node_id: str = typer.Argument(...),
    group: str = typer.Option(..., "--group", "-g", help="Security group (drive) · Security group (drive)"),
) -> None:
    """🇺🇸 One node's metadata plus its decrypted name — never its content (use `download` for that).

    🇧🇷 O metadado de um nó mais o nome decifrado — nunca o conteúdo (use `download` para isso).
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        drive = vault.drives.drive(group)
        node = drive.get(node_id)
    render_drive_node(console, drive, node, json_output=opts.json_output)
