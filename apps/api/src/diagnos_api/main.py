"""🇺🇸 `run()`: the `diagnos-api` console script (`[project.scripts]`) and `python -m diagnos_api`.

`diagnos-api` (or `diagnos-api serve`) serves; `diagnos-api dev-certs [DIR]`
writes a throwaway CA and certificates for a local run (`dev_certs.py`).

🇧🇷 `run()`: o script de console `diagnos-api` (`[project.scripts]`) e o `python -m diagnos_api`.

`diagnos-api` (ou `diagnos-api serve`) serve; `diagnos-api dev-certs [DIR]`
grava uma CA descartável e certificados para uma execução local (`dev_certs.py`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
from diagnos import ConfigError

from diagnos_api import dev_certs
from diagnos_api.app import create_app
from diagnos_api.logging import configure_logging
from diagnos_api.mtls import ClientCertH11Protocol, ssl_config_for_uvicorn
from diagnos_api.settings import ApiConfigError, ApiSettings


def run(argv: list[str] | None = None) -> None:
    """🇺🇸 `serve` (the default) or `dev-certs`. 🇧🇷 `serve` (o padrão) ou `dev-certs`."""
    parser = argparse.ArgumentParser(prog="diagnos-api", description="diagnos REST API · API REST do diagnos")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="Serve HTTPS with mandatory mTLS (default) · Serve HTTPS com mTLS obrigatório")
    certs = commands.add_parser(
        "dev-certs", help="Write a local CA and certificates · Grava uma CA e certificados locais"
    )
    certs.add_argument("directory", nargs="?", default="certs", type=Path, help="default · padrão: ./certs")
    certs.add_argument("--client-cn", default=dev_certs.DEFAULT_CLIENT_CN, help="Client certificate CN")
    certs.add_argument("--force", action="store_true", help="Replace existing files · Substitui arquivos")
    args = parser.parse_args(argv)
    if args.command == "dev-certs":
        _dev_certs(args.directory, client_cn=args.client_cn, force=args.force)
    else:
        serve()


def _dev_certs(directory: Path, *, client_cn: str, force: bool) -> None:
    """🇺🇸 Writes the certificates and prints what to run next. 🇧🇷 Grava os certificados e mostra o que rodar."""
    try:
        written = dev_certs.generate(directory, client_cn=client_cn, force=force)
    except dev_certs.DevCertsError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    exports = "\n".join(f"  export {name}={value}" for name, value in written.environment().items())
    print(
        f"Wrote a local CA and certificates to {directory}/ (valid {dev_certs.VALID_DAYS} days, local use only)\n"
        f"CA e certificados locais gravados em {directory}/ (válidos por {dev_certs.VALID_DAYS} dias, só uso local)\n\n"
        f"Run · Rode:\n  export DIAGNOS_API_TOKEN=apikey-…\n{exports}\n  diagnos-api\n\n"
        f"Call · Chame:\n  curl --cacert {written.ca} --cert {written.client} --key {written.client_key} "
        "https://localhost:8443/healthz"
    )


def serve() -> None:
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
