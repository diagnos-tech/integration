"""🇺🇸 Rendering for `files`: the node table (name decrypted per row) and one node's detail panel.

🇧🇷 Renderização para `files`: a tabela de nós (nome decifrado por linha) e o painel de detalhe de um nó.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from diagnos import GroupKeyUnavailable
from rich.table import Table

from diagnos_cli.render._shared import plain, record_panel
from diagnos_cli.render.json import print_json

if TYPE_CHECKING:
    from diagnos import Drive, DriveNode, Drives
    from rich.console import Console

LOCKED_NAME = "🔒"


def readable_name(reader: Drive | Drives, node: DriveNode) -> str | None:
    """🇺🇸 The node's decrypted name, or `None` when this session holds no key for its group.

    A workspace-wide listing can include groups the service account may list
    but whose key its enrollment was never handed; one such row must not
    take the whole table down — the same rule as document summaries.

    🇧🇷 O nome decifrado do nó, ou `None` quando esta sessão não tem chave para o grupo dele.

    Uma listagem do workspace inteiro pode incluir grupos que a service
    account pode listar mas cuja chave o enrollment dela nunca recebeu; uma
    linha dessas não pode derrubar a tabela inteira — a mesma regra dos
    resumos de documento.
    """
    try:
        return reader.name_of(node)
    except GroupKeyUnavailable:
        return None


def _as_json(node: DriveNode, name: str | None) -> dict[str, object]:
    """🇺🇸 `{node, name}` — the same shape the API answers. 🇧🇷 `{node, name}` — a mesma forma que a API responde."""
    return {"node": node, "name": name}


def human_size(num_bytes: int | None) -> str:
    """🇺🇸 `None` becomes `"—"`; otherwise the smallest unit that keeps the number under 1024.

    🇧🇷 `None` vira `"—"`; senão, a menor unidade que mantém o número abaixo de 1024.
    """
    if num_bytes is None:
        return "—"
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"  # pragma: no cover — unreachable for any real upload size


def render_drive_node_table(
    console: Console,
    drive: Drive | Drives,
    nodes: list[DriveNode],
    *,
    json_output: bool,
    next_cursor: str | None = None,
) -> None:
    """🇺🇸 A table of files and folders (a folder's name ends in `/`) — names decrypted once per row.

    Deliberately five columns, so it stays readable in an 80-column
    terminal; `files get` and `--json` carry the rest (group, MIME, folder).

    🇧🇷 Uma tabela de arquivos e pastas (o nome de uma pasta termina em `/`) — nomes decifrados uma vez por linha.

    Cinco colunas de propósito, para continuar legível num terminal de 80
    colunas; `files get` e `--json` trazem o resto (grupo, MIME, pasta).
    """
    names = [readable_name(drive, node) for node in nodes]
    if json_output:
        print_json(
            {
                "items": [_as_json(node, name) for node, name in zip(nodes, names, strict=True)],
                "next_cursor": next_cursor,
            }
        )
        return
    table = Table()
    table.add_column("Node ID")
    table.add_column("Name · Nome")
    table.add_column("Size · Tamanho", justify="right")
    table.add_column("Status")
    table.add_column("Exam · Exame")
    for node, name in zip(nodes, names, strict=True):
        shown = LOCKED_NAME if name is None else f"{name}/" if node.kind == "folder" else name
        table.add_row(
            plain(node.node_id),
            plain(shown),
            "—" if node.kind == "folder" else human_size(node.size),
            plain(node.status),
            plain(node.exam_id),
        )
    console.print(table)
    if not nodes:
        console.print("[dim]No results · Nenhum resultado[/dim]")
    if next_cursor:
        console.print(f"[dim]next cursor · próximo cursor: {plain(next_cursor)}[/dim]")


def render_drive_node(console: Console, drive: Drive | Drives, node: DriveNode, *, json_output: bool) -> None:
    """🇺🇸 One file's details, in a panel — `files get`.

    🇧🇷 Detalhes de um arquivo, num painel — `files get`.
    """
    name = readable_name(drive, node)
    if json_output:
        print_json(_as_json(node, name))
        return
    record_panel(
        console,
        f"File · Arquivo {node.node_id}",
        [
            ("name · nome", LOCKED_NAME if name is None else name),
            ("size · tamanho", human_size(node.size)),
            ("mime_type", node.mime_type),
            ("media_kind", node.media_kind),
            ("status", node.status),
            ("processing", node.processing_status),
            ("group · grupo", node.security_group_id),
            ("exam_id", node.exam_id),
            ("folder · pasta", node.parent_id),
            ("created_at", node.created_at),
        ],
    )
