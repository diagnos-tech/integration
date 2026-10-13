"""🇺🇸 The console scripts: `diagnos` picks the full CLI or the base; `diagnos-api` checks its extra first.

Both are installed with every copy of the package — one wheel, one set of
scripts — so neither may import a layer before knowing its extra is there.
`diagnos` is the full command line when `diagnos[cli]` is installed (it
still answers `docs`, `version`, `setup` and `help`), and the base
otherwise. `diagnos-api` without `diagnos[api]` prints the command that adds
it instead of a `ModuleNotFoundError` traceback.

🇧🇷 Os console scripts: `diagnos` escolhe a CLI completa ou a base; `diagnos-api` confere o extra antes.

Os dois são instalados com toda cópia do pacote — um wheel, um conjunto de
scripts — então nenhum pode importar uma camada antes de saber que o extra
dela está lá. O `diagnos` é a linha de comando completa quando o
`diagnos[cli]` está instalado (e ainda responde `docs`, `version`, `setup` e
`help`), e a base caso contrário. O `diagnos-api` sem `diagnos[api]` imprime
o comando que o soma em vez de um traceback de `ModuleNotFoundError`.
"""

from __future__ import annotations

import io
import sys
from typing import Final

from ._extras import MissingExtraError, installed
from ._wrapper import main as base
from ._wrapper.exit_codes import EXIT_UNAVAILABLE

# 🇺🇸 128 + SIGINT, what shells report for a command stopped with Ctrl+C.
# 🇧🇷 128 + SIGINT, o que os shells informam para um comando parado com Ctrl+C.
EXIT_INTERRUPTED: Final = 130


def _tolerant_streams() -> None:
    """🇺🇸 Never crash on a character the terminal's encoding lacks: it is replaced, the output goes on.

    🇧🇷 Nunca quebrar num caractere que a codificação do terminal não tem: ele é trocado, a saída continua.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def main() -> None:
    """🇺🇸 `diagnos`: the full CLI with `diagnos[cli]`, the base without it.

    🇧🇷 `diagnos`: a CLI completa com `diagnos[cli]`, a base sem ele.
    """
    _tolerant_streams()
    if installed("cli"):
        from .cli.main import app

        app()
        return
    try:
        code = base(sys.argv[1:])
    except KeyboardInterrupt:
        code = EXIT_INTERRUPTED
    raise SystemExit(code)


def api() -> None:
    """🇺🇸 `diagnos-api`: the REST API when `diagnos[api]` is installed.

    🇧🇷 `diagnos-api`: a API REST quando o `diagnos[api]` está instalado.
    """
    _tolerant_streams()
    if not installed("api"):
        print(MissingExtraError("api", "diagnos-api"), file=sys.stderr)
        raise SystemExit(EXIT_UNAVAILABLE)
    from .api.main import run

    run()
