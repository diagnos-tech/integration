"""🇺🇸 Rendering for `files`: the node table (name decrypted per row) and one node's detail panel.

🇧🇷 Renderização para `files`: a tabela de nós (nome decifrado por linha) e o painel de detalhe de um nó.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.table import Table

from diagnos_cli.render._shared import plain, record_panel
from diagnos_cli.render.json import print_json

if TYPE_CHECKING:
    from diagnos import DriveNode
    from rich.console import Console

# 🇺🇸 `vault.drives.drive(...)` returns an `diagnos.resources.drives.Drive` —
# the type every `README.md` example actually holds — but that class is not
# re-exported from top-level `diagnos` (SDK gap, reported separately).
# `CONVENTIONS.md` forbids reaching into `diagnos.resources` even just for a
# type hint, so `Drive` is annotated `Any` here instead of imported.
# 🇧🇷 `vault.drives.drive(...)` devolve uma `diagnos.resources.drives.Drive`
# — o tipo que todo exemplo do `README.md` de fato segura — mas essa classe
# não é reexportada por `diagnos` no topo (lacuna do SDK, relatada à parte).
# `CONVENTIONS.md` proíbe alcançar `diagnos.resources` mesmo só para um type
# hint, então `Drive` é anotado como `Any` aqui em vez de importado.
Drive = Any


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
    drive: Drive,
    nodes: list[DriveNode],
    *,
    json_output: bool,
) -> None:
    """🇺🇸 A table of drive nodes — `Drive.name_of` decrypts each name on demand, once per row.

    🇧🇷 Uma tabela de nós de drive — `Drive.name_of` decifra cada nome sob demanda, uma vez por linha.
    """
    if json_output:
        print_json({"items": nodes})
        return
    table = Table()
    table.add_column("Node ID")
    table.add_column("Name · Nome")
    table.add_column("Size · Tamanho")
    table.add_column("MIME")
    table.add_column("Status")
    table.add_column("Exam · Exame")
    for node in nodes:
        table.add_row(
            plain(node.node_id),
            plain(drive.name_of(node) or None),
            human_size(node.size),
            plain(node.mime_type),
            plain(node.status),
            plain(node.exam_id),
        )
    console.print(table)
    if not nodes:
        console.print("[dim]No results · Nenhum resultado[/dim]")


def render_drive_node(console: Console, drive: Drive, node: DriveNode, *, json_output: bool) -> None:
    """🇺🇸 One drive node's details, in a panel — `files get`.

    🇧🇷 Detalhes de um nó de drive, num painel — `files get`.
    """
    if json_output:
        print_json(node)
        return
    record_panel(
        console,
        f"File · Arquivo {node.node_id}",
        [
            ("name · nome", drive.name_of(node)),
            ("size · tamanho", human_size(node.size)),
            ("mime_type", node.mime_type),
            ("status", node.status),
            ("media_kind", node.media_kind),
            ("exam_id", node.exam_id),
            ("created_at", node.created_at),
        ],
    )
