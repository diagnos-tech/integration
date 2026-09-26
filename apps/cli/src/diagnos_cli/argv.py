"""🇺🇸 Lets global options come anywhere: `diagnos patients list --json` means `diagnos --json patients list`.

Typer only accepts a group's options before its subcommand, and "No such
option: --json" after it is the first mistake almost everyone makes. None
of these names is reused by a subcommand, so moving them to the front never
changes what a command means. Everything after `--` is left alone.

🇧🇷 Deixa as opções globais virem em qualquer lugar: `diagnos patients list --json` significa `diagnos --json
patients list`.

O Typer só aceita as opções de um grupo antes do subcomando, e "No such
option: --json" depois dele é o primeiro erro de quase todo mundo. Nenhum
destes nomes é reusado por um subcomando, então movê-los para a frente nunca
muda o que um comando significa. Tudo depois de `--` fica como está.
"""

from __future__ import annotations

from typing import Final

_FLAGS: Final = frozenset({"--json", "--quiet", "-q", "--no-color"})
_WITH_VALUE: Final = frozenset({"--token", "--vault-url"})


def hoist_global_options(argv: list[str]) -> list[str]:
    """🇺🇸 `argv` with every global option (and its value) moved before the first command word.

    🇧🇷 `argv` com toda opção global (e o valor dela) movida para antes da primeira palavra de comando.
    """
    hoisted: list[str] = []
    rest: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            rest.extend(argv[index:])
            break
        name = arg.partition("=")[0]
        if arg in _FLAGS:
            hoisted.append(arg)
        elif name in _WITH_VALUE:
            hoisted.append(arg)
            if "=" not in arg and index + 1 < len(argv):
                index += 1
                hoisted.append(argv[index])
        else:
            rest.append(arg)
        index += 1
    return hoisted + rest
