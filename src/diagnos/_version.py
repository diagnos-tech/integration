"""🇺🇸 The package version, read from the installed metadata — `pyproject.toml` is the single source of truth.

A hard-coded string here drifts from `pyproject.toml` on the first release
(and did, before this module existed); reading the metadata cannot.

🇧🇷 A versão do pacote, lida dos metadados instalados — `pyproject.toml` é a fonte única da verdade.

Uma string fixa aqui diverge do `pyproject.toml` no primeiro release (e
divergiu, antes deste módulo existir); ler os metadados não diverge.
"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from typing import Final

try:
    __version__ = version("diagnos")
except PackageNotFoundError:  # pragma: no cover — only a source tree nobody installed
    __version__ = "0.0.0+unknown"

# 🇺🇸 A version PyPI and GHCR can hold — no local (`+…`) or `.dev` segment. Only such a version is ever written into
#    a command (`diagnos[cli]==…`, an image tag); anything else is a development build.
# 🇧🇷 Uma versão que o PyPI e o GHCR podem ter — sem segmento local (`+…`) nem `.dev`. Só uma versão assim entra num
#    comando (`diagnos[cli]==…`, uma tag de imagem); qualquer outra é um build de desenvolvimento.
RELEASE: Final = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?")


def is_release(candidate: str) -> bool:
    """🇺🇸 Whether `candidate` is a release version, matched whole.

    🇧🇷 Se `candidate` é uma versão de release, casada por inteiro.
    """
    return RELEASE.fullmatch(candidate) is not None
