"""🇺🇸 Every place the CLI turns an SDK object into terminal output: tables, panels, `--json`.

Split by what is being rendered (`console.py` for the two `rich.Console`s,
`json.py` for `--json`, `documents.py` for `patients`/`exams`, `drives.py`
for `files`) instead of one growing file — `CONVENTIONS.md`'s "no file
above ~250 lines". Every command still writes `from diagnos_cli.render
import ...`: this `__init__.py` re-exports the whole public surface so the
split is invisible from outside the package.

🇧🇷 Todo lugar onde a CLI transforma um objeto do SDK em saída de terminal:
tabelas, painéis, `--json`.

Dividido pelo que está sendo renderizado (`console.py` para os dois
`rich.Console`, `json.py` para `--json`, `documents.py` para
`patients`/`exams`, `drives.py` para `files`) em vez de um arquivo só
crescendo — "nenhum arquivo acima de ~250 linhas" do `CONVENTIONS.md`. Todo
comando continua escrevendo `from diagnos_cli.render import ...`: este
`__init__.py` reexporta a superfície pública inteira para a divisão ficar
invisível de fora do pacote.
"""

from __future__ import annotations

from diagnos_cli.render.console import get_console, get_err_console
from diagnos_cli.render.documents import (
    render_document_index,
    render_exam,
    render_index_table,
    render_patient,
)
from diagnos_cli.render.drives import human_size, render_drive_node, render_drive_node_table
from diagnos_cli.render.json import print_json

__all__ = [
    "get_console",
    "get_err_console",
    "human_size",
    "print_json",
    "render_document_index",
    "render_drive_node",
    "render_drive_node_table",
    "render_exam",
    "render_index_table",
    "render_patient",
]
