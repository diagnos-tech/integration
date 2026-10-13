"""🇺🇸 `diagnos version` — this installation at a glance: version, interpreter, platform and which extras are in.

The first thing to paste into a bug report, and the quickest answer to "why
does `diagnos login` say it needs the CLI?": the interpreter's path shows
which environment answered, and each missing extra comes with the command
that adds it.

🇧🇷 `diagnos version` — esta instalação de relance: versão, interpretador, plataforma e quais extras estão dentro.

A primeira coisa a colar num relato de bug, e a resposta mais rápida para
"por que o `diagnos login` diz que precisa da CLI?": o caminho do
interpretador mostra qual ambiente respondeu, e cada extra ausente vem com o
comando que o soma.
"""

from __future__ import annotations

import platform
import sys
from typing import TypedDict

from .._extras import extras, install_hint, installed
from .._version import __version__
from .exit_codes import EXIT_OK
from .output import Output, table


class Installation(TypedDict):
    """🇺🇸 What `diagnos version --json` prints. 🇧🇷 O que o `diagnos version --json` imprime."""

    diagnos: str
    python: str
    implementation: str
    executable: str
    platform: str
    extras: dict[str, bool]


def installation() -> Installation:
    """🇺🇸 What `diagnos version --json` prints: versions, interpreter, platform, `{extra: installed}`.

    🇧🇷 O que o `diagnos version --json` imprime: versões, interpretador, plataforma, `{extra: instalado}`.
    """
    return {
        "diagnos": __version__,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "platform": f"{sys.platform}-{platform.machine().lower()}",
        "extras": {extra: installed(extra) for extra in extras()},
    }


def version(*, out: Output) -> int:
    """🇺🇸 Prints the installation, as text or JSON; always succeeds.

    🇧🇷 Imprime a instalação, como texto ou JSON; sempre dá certo.
    """
    info = installation()
    if out.json_output:
        out.data(info)
        return EXIT_OK
    out.line(out.style(f"diagnos {info['diagnos']}", "bold"))
    out.line(f"  python    {info['python']} ({info['implementation']}) · {info['executable']}")
    out.line(f"  platform  {info['platform']}")
    found = info["extras"]
    if not found:
        return EXIT_OK
    out.line()
    out.line(out.style("Extras · Extras", "bold"))
    rows = [
        (extra, "installed · instalado", "")
        if present
        else (extra, "not installed · não instalado", install_hint(extra))
        for extra, present in found.items()
    ]
    for (extra, _, _), row in zip(rows, table(rows), strict=True):
        out.line(row if found[extra] else out.style(row, "dim"))
    return EXIT_OK
