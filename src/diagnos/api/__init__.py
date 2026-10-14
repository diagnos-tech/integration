"""`diagnos.api`: the REST facade (FastAPI, mandatory mTLS) over the SDK (`diagnos[api]`).

`diagnos.api.main.run` is what the `diagnos-api` console script runs (through `diagnos._entry`);
`diagnos.api.app.create_app` is what tests build directly, against a fake `Diagnos`
(`apps/api/tests/conftest.py`). For everything vault-shaped this package imports only `diagnos` (`CONTRIBUTING.md`);
FastAPI, Starlette and uvicorn are its only other real dependencies. Importing it without the `api` extra raises
`MissingExtraError` with the command that installs it.
"""

from __future__ import annotations

from diagnos._extras import require

require("api", "diagnos.api")
