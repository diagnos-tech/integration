"""`run()`: the `diagnos-api` console script (`[project.scripts]`) and `python -m diagnos.api`.

`diagnos-api` (or `diagnos-api serve`) serves; `diagnos-api dev-certs [DIR]` writes a throwaway CA and certificates for
a local run (`dev_certs.py`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from diagnos import ConfigError
from diagnos.api import dev_certs
from diagnos.api.app import create_app
from diagnos.api.logging import configure_logging
from diagnos.api.mtls import ClientCertH11Protocol, ssl_config_for_uvicorn
from diagnos.api.settings import ApiConfigError, ApiSettings


def run(argv: list[str] | None = None) -> None:
    """Runs `serve` (the default) or `dev-certs`.

    Args:
        argv: The command-line arguments, without the program name. Defaults to `sys.argv[1:]`.
    """
    parser = argparse.ArgumentParser(prog="diagnos-api", description="diagnos REST API")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="Serve HTTPS with mandatory mTLS (default)")
    certs = commands.add_parser("dev-certs", help="Write a local CA and certificates")
    certs.add_argument("directory", nargs="?", default="certs", type=Path, help="default: ./certs")
    certs.add_argument("--client-cn", default=dev_certs.DEFAULT_CLIENT_CN, help="Client certificate CN")
    certs.add_argument("--force", action="store_true", help="Replace existing files")
    args = parser.parse_args(argv)
    if args.command == "dev-certs":
        _dev_certs(args.directory, client_cn=args.client_cn, force=args.force)
    else:
        serve()


def _dev_certs(directory: Path, *, client_cn: str, force: bool) -> None:
    """Writes the certificates and prints what to run next."""
    try:
        written = dev_certs.generate(directory, client_cn=client_cn, force=force)
    except dev_certs.DevCertsError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    exports = "\n".join(f"  export {name}={value}" for name, value in written.environment().items())
    print(
        f"Wrote a local CA and certificates to {directory}/ (valid {dev_certs.VALID_DAYS} days, local use only)\n\n"
        f"Run:\n  export DIAGNOS_API_TOKEN=apikey-…\n{exports}\n  diagnos-api\n\n"
        f"Call:\n  curl --cacert {written.ca} --cert {written.client} --key {written.client_key} "
        "https://localhost:8443/healthz"
    )


def serve() -> None:
    """Loads settings, builds the app and serves HTTPS with mandatory mTLS, or exits with code 2 and a clear reason.

    Both `ApiSettings.from_env()` (missing or malformed CA or TLS files) and `create_app` (missing
    `DIAGNOS_API_TOKEN`, via `diagnos.Settings.from_env` inside `Diagnos()`) can fail before a single request is
    served. Both cases print the message the exception already carries and exit with the same code, because either way
    this process has nothing safe to do but stop.
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
        # `None` stops uvicorn from installing its own logging config on top of `configure_logging()`'s, above.
        log_config=None,
        **ssl_config_for_uvicorn(settings),
    )


if __name__ == "__main__":
    run()
