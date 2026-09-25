"""🇺🇸 The one panel layout every decrypted-record and drive-node view shares.

🇧🇷 O único layout de painel que toda visão de registro decifrado e de nó de drive compartilha.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel


def record_panel(console: Console, title: str, fields: list[tuple[str, Any]]) -> None:
    """🇺🇸 A label/value line per field, `None` shown as `"—"` — used by `documents.py` and `drives.py`.

    Values are escaped: they are decrypted clinical data or vault-issued
    ids, and `rich` would otherwise read any `[...]` inside them as markup —
    silently dropping text (`[html]`) or restyling the terminal.

    🇧🇷 Uma linha rótulo/valor por campo, `None` mostrado como `"—"` — usado por `documents.py` e `drives.py`.

    Os valores são escapados: são dado clínico decifrado ou ids emitidos pelo
    cofre, e o `rich` leria qualquer `[...]` dentro deles como markup —
    sumindo com texto (`[html]`) ou mudando o estilo do terminal.
    """
    lines = [f"[bold]{label}[/bold]: {plain(value)}" for label, value in fields]
    console.print(Panel("\n".join(lines), title=title, expand=False))


def plain(value: Any) -> str:
    """🇺🇸 `value` as literal terminal text: `None` becomes `"—"` and `rich` markup is escaped.

    🇧🇷 `value` como texto literal no terminal: `None` vira `"—"` e o markup do `rich` é escapado.
    """
    return "—" if value is None else escape(str(value))
