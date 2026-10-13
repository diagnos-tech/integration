"""🇺🇸 `diagnos setup sdk` and `diagnos setup cli` — the Python layers, installed with `uv`.

The two differ in *where* the layer belongs. The SDK is a dependency of the
code someone is writing, so it goes into their project (`uv add`, which also
locks it) — or, outside any project, into the virtual environment they run
`diagnos` from, or a new project created right here. The CLI is a command,
so it goes where this `diagnos` runs, and the same `diagnos` gains every
command; from a `uv tool` (or a system Python that must not be written to)
it is installed as a `uv tool`.

🇧🇷 `diagnos setup sdk` e `diagnos setup cli` — as camadas Python, instaladas com `uv`.

As duas diferem em *onde* a camada pertence. O SDK é dependência do código
que alguém escreve, então vai para o projeto dessa pessoa (`uv add`, que
também o trava) — ou, fora de qualquer projeto, para o ambiente virtual de
onde ela roda o `diagnos`, ou para um projeto novo criado aqui mesmo. A CLI
é um comando, então vai para onde este `diagnos` roda, e o mesmo `diagnos`
ganha todo comando; a partir de um `uv tool` (ou de um Python de sistema que
não pode ser escrito) ela é instalada como `uv tool`.
"""

from __future__ import annotations

from pathlib import Path

from ..._extras import DISTRIBUTION, installed
from ..exit_codes import EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE
from ..output import Output
from .environment import Environment, project_name, project_root
from .run import Plan, command
from .tools import find, found, missing

_PROBE = 'python -c "from diagnos import Diagnos; print(Diagnos)"'
_QUICKSTART = "Quickstart · Início rápido: https://dev.diagnos.health"
CLI_NEXT = ("diagnos login", "diagnos --help")


def _development(out: Output) -> int:
    """🇺🇸 Explains why a development checkout is left alone.

    🇧🇷 Explica por que um checkout de desenvolvimento fica intocado.
    """
    out.error(
        "This is a development checkout: `uv sync` (or `make sync`) installs every extra · "
        "Isto é um checkout de desenvolvimento: o `uv sync` (ou `make sync`) instala todo extra."
    )
    return EXIT_FAILED


def _uv(out: Output, env: Environment, extra: str) -> str | None:
    """🇺🇸 The `uv` to run, announced — or `None` after saying how to get it (or go on with pip).

    🇧🇷 O `uv` a rodar, anunciado — ou `None` depois de dizer como obtê-lo (ou seguir com o pip).
    """
    uv = find("uv")
    if uv is None:
        missing(out, "uv", otherwise=f'python -m pip install "{env.requirement(extra)}"')
        return None
    found(out, "uv", uv)
    return uv


def sdk(out: Output, *, cwd: Path) -> Plan | int:
    """🇺🇸 The plan that puts the SDK where the code is, or the exit code when there is nothing to run.

    🇧🇷 O plano que põe o SDK onde está o código, ou o código de saída quando não há o que rodar.
    """
    env = Environment.current()
    project = project_root(cwd)
    if (project is not None and project_name(project) == DISTRIBUTION) or (project is None and env.development):
        return _development(out)
    uv = _uv(out, env, "sdk")
    if uv is None:
        return EXIT_UNAVAILABLE
    title = "Setup · sdk — the Python SDK · o SDK Python"
    floor = f"{DISTRIBUTION}[sdk]>={env.version}" if env.release else f"{DISTRIBUTION}[sdk]"
    if project is not None:
        add = (uv, "add", "--project", str(project), floor)
        summary = f"Add the SDK to {project / 'pyproject.toml'} · Soma o SDK ao {project / 'pyproject.toml'}"
        return Plan(title, (command(summary, add),), (f"uv run {_PROBE}", _QUICKSTART))
    if env.virtual and not env.uv_tool:
        if installed("sdk"):
            out.line("The SDK is already installed here · O SDK já está instalado aqui.")
            return EXIT_OK
        install = (uv, "pip", "install", "--python", env.python, env.requirement("sdk"))
        summary = "Add the SDK to this virtual environment · Soma o SDK a este ambiente virtual"
        return Plan(title, (command(summary, install),), (_PROBE, _QUICKSTART))
    steps = (
        command(
            f"Create a Python project in {cwd} · Cria um projeto Python em {cwd}",
            (uv, "init", "--bare", "--no-workspace", str(cwd)),
        ),
        command(
            "Add the SDK to it · Soma o SDK a ele",
            (uv, "add", "--project", str(cwd), floor),
        ),
    )
    return Plan(title, steps, (f"uv run {_PROBE}", _QUICKSTART))


def cli(out: Output) -> Plan | int:
    """🇺🇸 The plan that gives this `diagnos` every command, or the exit code when there is nothing to run.

    🇧🇷 O plano que dá a este `diagnos` todo comando, ou o código de saída quando não há o que rodar.
    """
    env = Environment.current()
    if installed("cli"):
        out.line("The full command line is already installed · A linha de comando completa já está instalada.")
        out.line(f"  {CLI_NEXT[1]}")
        return EXIT_OK
    if env.development:
        return _development(out)
    uv = _uv(out, env, "cli")
    if uv is None:
        return EXIT_UNAVAILABLE
    title = "Setup · cli — the full command line · a linha de comando completa"
    install: tuple[str, ...]
    if env.uv_tool or env.externally_managed:
        install = (uv, "tool", "install", env.requirement("cli"))
        summary = "Install the CLI as a uv tool · Instala a CLI como ferramenta do uv"
    else:
        install = (uv, "pip", "install", "--python", env.python, env.requirement("cli"))
        summary = "Add the CLI to the environment that runs diagnos · Soma a CLI ao ambiente que roda o diagnos"
    return Plan(title, (command(summary, install),), CLI_NEXT)
