"""🇺🇸 The programs `setup` relies on — `uv`, Docker, cosign — found on `PATH`, never fetched or installed by us.

`find` walks `PATH` itself instead of `shutil.which`: on Windows, `which`
looks in the current folder first, and any relative entry (`.`) does the
same everywhere — a planted `uv` in a downloaded folder would then run as
if it were the real one. Only absolute entries count, and on Windows only
`.exe` files: a `.bat`/`.cmd` would go through `cmd.exe`, which re-parses
its arguments.

A missing program is reported with its official install page; `setup`
never downloads an installer or pipes one into a shell on anyone's behalf.

🇧🇷 Os programas de que o `setup` depende — `uv`, Docker, cosign — achados no `PATH`, nunca baixados nem instalados.

O `find` percorre o `PATH` ele mesmo em vez do `shutil.which`: no Windows o
`which` olha a pasta atual primeiro, e qualquer entrada relativa (`.`) faz o
mesmo em todo lugar — um `uv` plantado numa pasta baixada rodaria como se
fosse o de verdade. Só entradas absolutas contam, e no Windows só arquivos
`.exe`: um `.bat`/`.cmd` passaria pelo `cmd.exe`, que reinterpreta os
argumentos.

Um programa ausente é relatado com a página oficial de instalação; o `setup`
nunca baixa um instalador nem o joga num shell em nome de ninguém.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from ..output import Output, printable

INSTALL_PAGES: Final = {
    "uv": "https://docs.astral.sh/uv/getting-started/installation/",
    "docker": "https://docs.docker.com/get-started/get-docker/",
    "cosign": "https://docs.sigstore.dev/cosign/system_config/installation/",
}
_DAEMON_TIMEOUT_SECONDS: Final = 20


def find(name: str, env: Mapping[str, str] = os.environ) -> str | None:
    """🇺🇸 The absolute path of executable `name` on `PATH`, skipping relative entries; `None` if absent.

    🇧🇷 O caminho absoluto do executável `name` no `PATH`, pulando entradas relativas; `None` se ausente.
    """
    filename = f"{name}.exe" if os.name == "nt" else name
    for entry in env.get("PATH", "").split(os.pathsep):
        folder = Path(entry)
        if not entry or not folder.is_absolute():
            continue
        candidate = folder / filename
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def docker_running(docker: str) -> bool:
    """🇺🇸 Whether the Docker daemon answers — an installed `docker` with a stopped engine cannot pull.

    🇧🇷 Se o daemon do Docker responde — um `docker` instalado com o motor parado não consegue baixar.
    """
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, absolute path from `find`
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=_DAEMON_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def found(out: Output, name: str, path: str) -> None:
    """🇺🇸 One line saying which `name` will run. 🇧🇷 Uma linha dizendo qual `name` vai rodar."""
    out.line(f"{out.style(name, 'green')} found · encontrado: {printable(path)}")


def missing(out: Output, name: str, *, otherwise: str | None = None) -> None:
    """🇺🇸 Says `name` is missing, where to get it, and (`otherwise`) how to go on without it.

    🇧🇷 Diz que `name` falta, onde obtê-lo, e (`otherwise`) como seguir sem ele.
    """
    out.error(f"{out.style(name, 'red')} not found · não encontrado.")
    out.error(f"  Install it, then run this again · Instale e rode isto de novo: {INSTALL_PAGES[name]}")
    if otherwise:
        out.error(f"  Or, without {name} · Ou, sem {name}: {otherwise}")
