"""🇺🇸 Where this `diagnos` runs — the facts that decide how `setup` installs a layer.

Installing an extra means "into the environment that runs `diagnos`", so
the new commands appear on the very `diagnos` that was typed. Three cases
change how: a `uv tool` environment (re-installed through `uv tool`, so its
receipt keeps the extra across upgrades), a system interpreter outside any
virtual environment (never written to — PEP 668, and possibly root; a
`uv tool` instead), and a development build (an editable install or a
version no release carries — `uv sync` already gives it every extra, and a
release from PyPI must not replace it).

🇧🇷 Onde este `diagnos` roda — os fatos que decidem como o `setup` instala uma camada.

Instalar um extra significa "no ambiente que roda o `diagnos`", para os
comandos novos aparecerem no próprio `diagnos` digitado. Três casos mudam o
como: um ambiente `uv tool` (reinstalado pelo `uv tool`, para o recibo dele
manter o extra entre upgrades), um interpretador de sistema fora de
qualquer ambiente virtual (nunca escrito — PEP 668, e talvez root; um
`uv tool` no lugar), e um build de desenvolvimento (uma instalação editável
ou uma versão que nenhum release tem — o `uv sync` já lhe dá todo extra, e
um release do PyPI não pode substituí-lo).
"""

from __future__ import annotations

import json
import sys
import tomllib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from ..._extras import DISTRIBUTION
from ..._version import __version__, is_release


@dataclass(frozen=True)
class Environment:
    """🇺🇸 The interpreter running `diagnos`, and how this copy of `diagnos` got into it.

    🇧🇷 O interpretador que roda o `diagnos`, e como esta cópia do `diagnos` chegou nele.
    """

    python: str
    version: str
    editable: bool
    uv_tool: bool
    virtual: bool

    @classmethod
    def current(cls) -> Environment:
        """🇺🇸 This process's environment. 🇧🇷 O ambiente deste processo."""
        prefix = Path(sys.prefix)
        virtual = sys.prefix != sys.base_prefix
        return cls(
            python=sys.executable,
            version=__version__,
            editable=_editable(),
            # 🇺🇸 `uv tool install` writes this receipt at the root of every tool environment.
            # 🇧🇷 O `uv tool install` grava este recibo na raiz de todo ambiente de ferramenta.
            uv_tool=(prefix / "uv-receipt.toml").is_file(),
            virtual=virtual,
        )

    @property
    def release(self) -> bool:
        """🇺🇸 Whether PyPI and GHCR can have this version. 🇧🇷 Se o PyPI e o GHCR podem ter esta versão."""
        return is_release(self.version)

    @property
    def development(self) -> bool:
        """🇺🇸 An editable install, or a version no release carries: never replaced by one from PyPI.

        🇧🇷 Uma instalação editável, ou uma versão que nenhum release tem: nunca substituída por uma do PyPI.
        """
        return self.editable or not self.release

    def requirement(self, extra: str) -> str:
        """🇺🇸 `diagnos[extra]==<this version>`: adds the layer and leaves the version alone (unpinned on a dev build).

        🇧🇷 `diagnos[extra]==<esta versão>`: soma a camada e deixa a versão como está (sem fixar num build de dev).
        """
        return f"{DISTRIBUTION}[{extra}]=={self.version}" if self.release else f"{DISTRIBUTION}[{extra}]"


def _editable() -> bool:
    """🇺🇸 Whether `diagnos` is an editable install (PEP 610), or no install at all (a bare source tree).

    🇧🇷 Se o `diagnos` é uma instalação editável (PEP 610), ou nenhuma instalação (uma árvore de fontes solta).
    """
    try:
        text = distribution(DISTRIBUTION).read_text("direct_url.json")
    except PackageNotFoundError:
        return True
    try:
        origin = json.loads(text) if text else {}
    except ValueError:
        return False
    return bool(isinstance(origin, dict) and origin.get("dir_info", {}).get("editable", False))


def project_root(start: Path) -> Path | None:
    """🇺🇸 The nearest folder from `start` upward with a `pyproject.toml` — where `uv add` would write.

    🇧🇷 A pasta mais próxima de `start` para cima com um `pyproject.toml` — onde o `uv add` escreveria.
    """
    for folder in (start, *start.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    return None


def project_name(root: Path) -> str | None:
    """🇺🇸 `[project].name` of the `pyproject.toml` in `root`, or `None` when unreadable or unnamed.

    🇧🇷 O `[project].name` do `pyproject.toml` em `root`, ou `None` quando ilegível ou sem nome.
    """
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            name = tomllib.load(handle).get("project", {}).get("name")
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return name if isinstance(name, str) else None
