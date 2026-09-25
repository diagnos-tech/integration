"""🇺🇸 The package version, read from the installed metadata — `pyproject.toml` is the single source of truth.

A hard-coded string here drifts from `pyproject.toml` on the first release
(and did, before this module existed); reading the metadata cannot.

🇧🇷 A versão do pacote, lida dos metadados instalados — `pyproject.toml` é a fonte única da verdade.

Uma string fixa aqui diverge do `pyproject.toml` no primeiro release (e
divergiu, antes deste módulo existir); ler os metadados não diverge.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("diagnos-api")
except PackageNotFoundError:  # pragma: no cover — only a source tree nobody installed
    __version__ = "0.0.0+unknown"
