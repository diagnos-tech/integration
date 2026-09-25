"""🇺🇸 The one panel layout every decrypted-record and drive-node view shares.

🇧🇷 O único layout de painel que toda visão de registro decifrado e de nó de drive compartilha.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel


def record_panel(console: Console, title: str, fields: list[tuple[str, Any]]) -> None:
    """🇺🇸 A label/value line per field, `None` shown as `"—"` — used by `documents.py` and `drives.py`.

    🇧🇷 Uma linha rótulo/valor por campo, `None` mostrado como `"—"` — usado por `documents.py` e `drives.py`.
    """
    lines = [f"[bold]{label}[/bold]: {value if value is not None else '—'}" for label, value in fields]
    console.print(Panel("\n".join(lines), title=title, expand=False))
