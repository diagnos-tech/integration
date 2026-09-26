"""🇺🇸 `diagnos files` — list, upload, mkdir, download, get: the workspace's files and folders.

A file belongs to one security group, so `upload` and `mkdir` take
`--group`; reading a file needs only its node id. `upload_many` has no
progress callback (one blocking call per batch), so the progress below shows
one row per file and that a batch is in flight — never faked byte counts.

🇧🇷 `diagnos files` — listar, subir, criar pasta, baixar, ler: os arquivos e pastas do workspace.

Um arquivo pertence a um security group, então `upload` e `mkdir` recebem
`--group`; ler um arquivo precisa só do id do nó. `upload_many` não tem
callback de progresso (uma chamada bloqueante por lote), então o progresso
abaixo mostra uma linha por arquivo e que um lote está em voo — nunca
contagem de bytes inventada.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from diagnos import DriveNode
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.examples import examples
from diagnos_cli.render import get_console, get_err_console, print_json, render_drive_node, render_drive_node_table
from diagnos_cli.render._shared import plain

if TYPE_CHECKING:
    from diagnos import Drive

app = typer.Typer(help="Files and folders · Arquivos e pastas")

_FOLDER_HELP = "Folder node id · Id do nó da pasta"
_NODE_HELP = "File node id · Id do nó do arquivo"


def safe_file_name(name: str | None, fallback: str) -> str:
    """🇺🇸 A decrypted name made safe to write in the current directory: its last path segment only.

    The name comes from the vault, sealed by whoever uploaded the file — the
    web app stores a relative path there. Using it as a path as-is would let
    `../../.bashrc` write outside the working directory.

    🇧🇷 Um nome decifrado tornado seguro para gravar no diretório atual: só o último segmento do caminho.

    O nome vem do cofre, selado por quem subiu o arquivo — o app web guarda
    ali um caminho relativo. Usá-lo como caminho sem tratar deixaria
    `../../.bashrc` gravar fora do diretório de trabalho.
    """
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return base if base not in ("", ".", "..") else fallback


@app.command(
    "list",
    help="List files and folders (one page, or all with --all) · Lista arquivos e pastas (uma página, ou --all)",
    epilog=examples(
        (
            "diagnos files list --group sg_oncology --folder FOLDER_ID",
            "One folder, names decrypted · Uma pasta, nomes decifrados",
        ),
        (
            "diagnos --json files list --exam EXAM_ID --all",
            "Every file linked to an exam, as JSON · Todo arquivo ligado a um exame, em JSON",
        ),
    ),
)
def list_files(
    ctx: typer.Context,
    group: str | None = typer.Option(None, "--group", "-g", help="Security group filter · Filtro de security group"),
    exam: str | None = typer.Option(None, "--exam", help="Filter by exam id · Filtra por id de exame"),
    folder: str | None = typer.Option(None, "--folder", help=_FOLDER_HELP),
    include_pending: bool = typer.Option(False, "--include-pending", help="Include pending · Inclui pendentes"),
    limit: int = typer.Option(50, "--limit", help="Page size · Tamanho da página"),
    cursor: str | None = typer.Option(None, "--cursor", help="Resume from this cursor · Retoma a partir deste cursor"),
    all_pages: bool = typer.Option(False, "--all", help="Walk every page · Percorre todas as páginas"),
) -> None:
    """🇺🇸 One page of nodes (names decrypted per row), or every page with `--all`.

    🇧🇷 Uma página de nós (nomes decifrados por linha), ou todas as páginas com `--all`.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    filters: dict[str, Any] = {
        "security_group": group,
        "exam_id": exam,
        "parent_id": folder,
        "include_pending": include_pending,
        "limit": limit,
    }
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        drives = vault.drives
        if all_pages:
            nodes = list(drives.iter_all(**filters))
            next_cursor = None
        else:
            page = drives.list(**filters, cursor=cursor)
            nodes, next_cursor = list(page.items), page.next_cursor
    render_drive_node_table(console, drives, nodes, json_output=opts.json_output, next_cursor=next_cursor)


def _upload_with_progress(
    console: Console, drive: Drive, paths: list[Path], *, exam_id: str | None, parent_id: str | None, quiet: bool
) -> list[DriveNode]:
    """🇺🇸 One progress row per file; every row completes together, since `upload_many` is one blocking call.

    🇧🇷 Uma linha de progresso por arquivo; toda linha completa junto, já que `upload_many` é uma chamada bloqueante.
    """
    sources = [str(path) for path in paths]
    if quiet:
        return drive.upload_many(sources, exam_id=exam_id, parent_id=parent_id)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        tasks = [progress.add_task(path.name, total=1) for path in paths]
        nodes = drive.upload_many(sources, exam_id=exam_id, parent_id=parent_id)
        for task_id in tasks:
            progress.update(task_id, completed=1)
    return nodes


@app.command(
    "upload",
    help="Encrypt and upload files · Cifra e envia arquivos",
    epilog=examples(
        (
            "diagnos files upload --group sg_oncology --exam EXAM_ID scans/IM-0001.dcm scans/IM-0002.dcm",
            "Encrypt a series and link it to an exam · Cifra uma série e liga a um exame",
        ),
        (
            "diagnos files upload --group sg_oncology --folder FOLDER_ID report.pdf",
            "Into a folder · Dentro de uma pasta",
        ),
    ),
)
def upload_files(
    ctx: typer.Context,
    paths: list[Path] = typer.Argument(..., help="Files to upload · Arquivos para subir"),
    group: str = typer.Option(..., "--group", "-g", help="Security group to seal under · Grupo sob o qual selar"),
    exam: str | None = typer.Option(None, "--exam", help="Attach to this exam id · Vincula a este id de exame"),
    folder: str | None = typer.Option(None, "--folder", help=_FOLDER_HELP),
) -> None:
    """🇺🇸 Uploads every path (reserved 100 at a time); each file gets its own key, named after its file name.

    🇧🇷 Sobe todo path (reservado de 100 em 100); cada arquivo ganha a própria chave, nomeado pelo nome do arquivo.
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
        nodes = _upload_with_progress(err_console, drive, paths, exam_id=exam, parent_id=folder, quiet=opts.quiet)
    render_drive_node_table(console, drive, nodes, json_output=opts.json_output)


@app.command(
    "mkdir",
    help="Create a folder · Cria uma pasta",
    epilog=examples(
        (
            'diagnos files mkdir "CT 2026-09-01" --group sg_oncology',
            "Prints the new folder's node id · Imprime o id do nó da pasta nova",
        ),
        (
            "diagnos --json files mkdir Series --group sg_oncology --parent FOLDER_ID",
            "A subfolder, id as JSON · Uma subpasta, id em JSON",
        ),
    ),
)
def make_folder(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Folder name (sealed) · Nome da pasta (selado)"),
    group: str = typer.Option(..., "--group", "-g", help="Security group to seal under · Grupo sob o qual selar"),
    parent: str | None = typer.Option(None, "--parent", help="Parent folder node id · Id do nó da pasta-mãe"),
) -> None:
    """🇺🇸 Creates a folder and prints its node id — pass it to `upload --folder`.

    🇧🇷 Cria uma pasta e imprime o id do nó — passe-o para `upload --folder`.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        folder_id = vault.drives.drive(group).create_folder(name, parent_id=parent)
    if opts.json_output:
        print_json({"node_id": folder_id})
    else:
        console.print(folder_id, markup=False)


@app.command(
    "download",
    help="Download and decrypt one file · Baixa e decifra um arquivo",
    epilog=examples(
        (
            "diagnos files download NODE_ID",
            "Saved under its decrypted name, in this folder · Salvo com o nome decifrado, nesta pasta",
        ),
        ("diagnos files download NODE_ID -o scan.dcm", "Saved where you say · Salvo onde você mandar"),
    ),
)
def download_file(
    ctx: typer.Context,
    node_id: str = typer.Argument(..., help=_NODE_HELP),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination path (default: the decrypted file name) · Destino (padrão: o nome decifrado)",
    ),
) -> None:
    """🇺🇸 Downloads and decrypts one file, to `--output` or to its decrypted name in the current directory.

    🇧🇷 Baixa e decifra um arquivo, para `--output` ou para o nome decifrado no diretório atual.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        drives = vault.drives
        if output is None:
            output = Path(safe_file_name(drives.name_of(drives.get(node_id)), node_id))
        status = None if opts.quiet else err_console.status("[cyan]downloading… · baixando…[/cyan]", spinner="dots")
        if status is not None:
            status.start()
        try:
            drives.download(node_id, output)
        finally:
            if status is not None:
                status.stop()

    if opts.json_output:
        print_json({"node_id": node_id, "saved_to": str(output)})
    elif not opts.quiet:
        console.print(f"[green]Saved · Salvo:[/green] {plain(output)}", highlight=False)


@app.command(
    "get",
    help="Show one file's metadata and name · Mostra metadados e nome de um arquivo",
    epilog=examples(
        (
            "diagnos files get NODE_ID",
            "Metadata and the decrypted name, never the content · Metadados e o nome decifrado, nunca o conteúdo",
        )
    ),
)
def get_file(ctx: typer.Context, node_id: str = typer.Argument(..., help=_NODE_HELP)) -> None:
    """🇺🇸 One file's metadata plus its decrypted name — never its content (use `download` for that).

    🇧🇷 O metadado de um arquivo mais o nome decifrado — nunca o conteúdo (use `download` para isso).
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        drives = vault.drives
        node = drives.get(node_id)
    render_drive_node(console, drives, node, json_output=opts.json_output)
