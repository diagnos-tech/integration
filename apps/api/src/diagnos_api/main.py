"""🇺🇸 `run()`: the `diagnos-api` console script's entry point (`pyproject.toml`'s `[project.scripts]`).

🇧🇷 `run()`: o ponto de entrada do script de console `diagnos-api` (`[project.scripts]` do `pyproject.toml`).
"""

from __future__ import annotations

import sys

import uvicorn
from diagnos import ConfigError

from diagnos_api.app import create_app
from diagnos_api.logging import configure_logging
from diagnos_api.mtls import ClientCertH11Protocol, ssl_config_for_uvicorn
from diagnos_api.settings import ApiConfigError, ApiSettings


def run() -> None:
    """🇺🇸 Loads settings, builds the app, serves HTTPS with mandatory mTLS — or exits(2) with a clear reason.

    Both `ApiSettings.from_env()` (missing/malformed CA or TLS files) and
    `create_app` (missing `DIAGNOS_API_TOKEN`, via `diagnos.Settings.from_env`
    inside `Diagnos()`) can fail before a single request is ever served;
    both cases print the bilingual message the exception already carries and
    exit with the same code, because either way this process has nothing
    safe to do but stop.

    🇧🇷 Carrega configuração, constrói o app, serve HTTPS com mTLS
    obrigatório — ou sai com código 2 e um motivo claro.

    Tanto `ApiSettings.from_env()` (CA ou arquivos de TLS ausentes ou
    malformados) quanto `create_app` (`DIAGNOS_API_TOKEN` ausente, via
    `diagnos.Settings.from_env` dentro de `Diagnos()`) podem falhar antes de
    qualquer requisição ser servida; os dois casos imprimem a mensagem
    bilíngue que a exceção já carrega e saem com o mesmo código, porque de
    um jeito ou de outro este processo não tem nada seguro a fazer além de
    parar.
    """
    configure_logging()

    try:
        settings = ApiSettings.from_env()
    except ApiConfigError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    try:
        app = create_app(settings)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        http=ClientCertH11Protocol,
        # 🇺🇸 `None` stops uvicorn from installing its own logging config on
        # top of `configure_logging()`'s, above.
        # 🇧🇷 `None` impede o uvicorn de instalar a própria configuração de
        # logging por cima da de `configure_logging()`, acima.
        log_config=None,
        **ssl_config_for_uvicorn(settings),
    )


if __name__ == "__main__":
    run()
