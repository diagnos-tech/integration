"""🇺🇸 Which extras of `diagnos` this environment has — and the error that says how to add a missing one.

`pip install diagnos` ships every layer's code in one wheel; an extra only
adds a layer's dependencies (`diagnos[sdk]`, `diagnos[cli]`, `diagnos[api]`).
So "is the CLI here?" is a question about installed distributions, and the
`Requires-Dist` lines `pyproject.toml` wrote into the metadata answer it
without importing anything heavy — the base stays fast and standard-library
only. Versions are not compared: a present distribution counts, and a real
incompatibility still surfaces as the import error it is.

🇧🇷 Quais extras do `diagnos` este ambiente tem — e o erro que diz como somar um que falta.

O `pip install diagnos` traz o código de toda camada num wheel só; um extra
só soma as dependências de uma camada (`diagnos[sdk]`, `diagnos[cli]`,
`diagnos[api]`). Então "a CLI está aqui?" é uma pergunta sobre distribuições
instaladas, e as linhas `Requires-Dist` que o `pyproject.toml` gravou nos
metadados respondem sem importar nada pesado — a base continua rápida e só
com a biblioteca padrão. Versões não são comparadas: uma distribuição
presente conta, e uma incompatibilidade de verdade ainda aparece como o erro
de import que ela é.
"""

from __future__ import annotations

import re
from functools import cache
from importlib.metadata import PackageNotFoundError, distribution
from typing import Final

DISTRIBUTION: Final = "diagnos"
# 🇺🇸 The extras `diagnos setup` walks through; the others are one `pip install` away.
# 🇧🇷 Os extras que o `diagnos setup` conduz passo a passo; os outros estão a um `pip install`.
GUIDED: Final = ("sdk", "cli", "api")

_REQUIREMENT: Final = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[(?P<extras>[^\]]*)\])?[^;]*(?:;(?P<marker>.*))?$"
)
_EXTRA_MARKER: Final = re.compile(r"""^\s*extra\s*==\s*["'](?P<extra>[^"']+)["']\s*$""")

Requirement = tuple[str, tuple[str, ...]]


class MissingExtraError(ImportError):
    """🇺🇸 A feature was used without its extra; the message is the command that adds it.

    An `ImportError`, so the usual "is this optional dependency here?"
    handling keeps working.

    🇧🇷 Um recurso foi usado sem o extra dele; a mensagem é o comando que o soma.

    Um `ImportError`, para o tratamento usual de "esta dependência opcional
    está aqui?" continuar funcionando.
    """

    def __init__(self, extra: str, feature: str) -> None:
        self.extra = extra
        super().__init__(
            f"{feature} needs the `{extra}` extra · {feature} precisa do extra `{extra}`: {install_hint(extra)}",
            name=DISTRIBUTION,
        )


def install_hint(extra: str) -> str:
    """🇺🇸 How to add `extra`, as one line to copy. 🇧🇷 Como somar `extra`, numa linha para copiar."""
    command = f'pip install "{DISTRIBUTION}[{extra}]"'
    return f"{command} (or · ou: diagnos setup {extra})" if extra in GUIDED else command


@cache
def _declared() -> dict[str, tuple[Requirement, ...]] | None:
    """🇺🇸 `{extra: ((distribution, its extras), …)}` from the metadata; `None` for a source tree nobody installed.

    🇧🇷 `{extra: ((distribuição, extras dela), …)}` dos metadados; `None` numa árvore de fontes nunca instalada.
    """
    try:
        meta = distribution(DISTRIBUTION)
    except PackageNotFoundError:
        return None
    found: dict[str, list[Requirement]] = {extra: [] for extra in meta.metadata.get_all("Provides-Extra") or []}
    for line in meta.requires or []:
        match = _REQUIREMENT.match(line)
        marker = _EXTRA_MARKER.match(match["marker"] or "") if match else None
        if match is None or marker is None:
            continue
        extras = tuple(part.strip() for part in (match["extras"] or "").split(",") if part.strip())
        found.setdefault(marker["extra"], []).append((match["name"], extras))
    return {extra: tuple(requirements) for extra, requirements in found.items()}


def _normalized(name: str) -> str:
    """🇺🇸 The PEP 503 form of a distribution name. 🇧🇷 A forma PEP 503 de um nome de distribuição."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _present(name: str) -> bool:
    """🇺🇸 Whether distribution `name` is installed. 🇧🇷 Se a distribuição `name` está instalada."""
    try:
        distribution(name)
    except PackageNotFoundError:
        return False
    return True


def extras() -> tuple[str, ...]:
    """🇺🇸 Every extra `diagnos` declares: the guided layers first, then the rest alphabetically.

    Empty for a source tree nobody installed.

    🇧🇷 Todo extra que o `diagnos` declara: as camadas guiadas primeiro, depois o resto em ordem alfabética.

    Vazio numa árvore de fontes nunca instalada.
    """
    declared = _declared() or {}
    return (*(extra for extra in GUIDED if extra in declared), *sorted(set(declared) - set(GUIDED)))


def installed(extra: str) -> bool:
    """🇺🇸 Whether every dependency of `extra` (and of the extras it names) is installed.

    A source tree nobody installed has no metadata to read: it answers
    `True` and lets the import itself say what is missing.

    🇧🇷 Se toda dependência de `extra` (e dos extras que ele nomeia) está instalada.

    Uma árvore de fontes nunca instalada não tem metadados para ler: responde
    `True` e deixa o próprio import dizer o que falta.
    """
    declared = _declared()
    if declared is None:
        return True
    if extra not in declared:
        raise ValueError(f"diagnos has no extra · não tem o extra {extra!r}")
    pending, seen = [extra], set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        for name, nested in declared.get(current, ()):
            if _normalized(name) == DISTRIBUTION:
                pending.extend(nested)
            elif not _present(name):
                return False
    return True


def require(extra: str, feature: str) -> None:
    """🇺🇸 Raises `MissingExtraError` when `extra` is not installed; `feature` names what needed it.

    🇧🇷 Lança `MissingExtraError` quando `extra` não está instalado; `feature` nomeia o que precisou dele.
    """
    if not installed(extra):
        raise MissingExtraError(extra, feature)
