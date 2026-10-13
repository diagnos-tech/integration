"""🇺🇸 `diagnos.api` — the REST facade (FastAPI, mandatory mTLS) over the SDK (`diagnos[api]`).

`diagnos.api.main.run` is what the `diagnos-api` console script runs
(through `diagnos._entry`); `diagnos.api.app.create_app` is what tests build
directly, against a fake `Diagnos` (`apps/api/tests/conftest.py`). This
package imports only `diagnos` for everything vault-shaped
(`CONTRIBUTING.md`) — FastAPI/Starlette/uvicorn are its only other real
dependencies. Importing it without the `api` extra raises
`MissingExtraError` with the command that adds it.

🇧🇷 `diagnos.api` — a fachada REST (FastAPI, mTLS obrigatório) sobre o SDK (`diagnos[api]`).

`diagnos.api.main.run` é o que o console script `diagnos-api` roda (pelo
`diagnos._entry`); `diagnos.api.app.create_app` é o que os testes constroem
direto, contra um `Diagnos` falso (`apps/api/tests/conftest.py`). Este
pacote importa só `diagnos` para tudo relacionado ao cofre
(`CONTRIBUTING.pt-BR.md`) — FastAPI/Starlette/uvicorn são suas únicas outras
dependências de verdade. Importá-lo sem o extra `api` lança
`MissingExtraError` com o comando que o soma.
"""

from __future__ import annotations

from diagnos._extras import require

require("api", "diagnos.api")
