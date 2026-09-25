"""🇺🇸 diagnos-api — REST facade (FastAPI, mandatory mTLS) over the diagnos SDK.

`diagnos_api.main.run` is the console script's entry point
(`pyproject.toml`); `diagnos_api.app.create_app` is what tests build
directly, against a fake `Diagnos` (`tests/conftest.py`). This package
imports only `diagnos` for everything vault-shaped (`CONVENTIONS.md`) —
FastAPI/Starlette/uvicorn are its only other real dependencies.

🇧🇷 diagnos-api — fachada REST (FastAPI, mTLS obrigatório) sobre o SDK
diagnos.

`diagnos_api.main.run` é o ponto de entrada do script de console
(`pyproject.toml`); `diagnos_api.app.create_app` é o que os testes
constroem direto, contra um `Diagnos` falso (`tests/conftest.py`). Este
pacote importa só `diagnos` para tudo relacionado ao cofre
(`CONVENTIONS.md`) — FastAPI/Starlette/uvicorn são suas únicas outras
dependências de verdade.
"""

from __future__ import annotations

from ._version import __version__ as __version__
