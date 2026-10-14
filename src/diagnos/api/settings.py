"""`ApiSettings`: everything the API process itself needs, read once from the environment.

This is deliberately separate from `diagnos.Settings`, the SDK's own configuration. `ApiSettings` only knows the
HTTP/mTLS concerns of *this process* (which port to bind, which certificate pair to serve, which CA signs the callers
it trusts) and never touches the vault credential or the OpenBao configuration. Those stay in
`diagnos.Settings.from_env()`, read independently wherever a `Diagnos` is constructed (`app.py`), so the two
configurations can never drift into reading the same variable in two different ways.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

# `0.0.0.0` is the documented default (`deploy/README.md`) precisely because mTLS, not network placement, is what keeps
# this process safe to expose: every request is TLS-terminated here and rejected at the handshake without a client
# certificate the trusted CA signed, so binding every interface costs nothing that a firewall was not already
# responsible for.
DEFAULT_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_PORT = 8443

_CA_VAR = "DIAGNOS_API_MTLS_CA_FILE"
_CERT_VAR = "DIAGNOS_API_TLS_CERT_FILE"
_KEY_VAR = "DIAGNOS_API_TLS_KEY_FILE"
_HOST_VAR = "DIAGNOS_API_HOST"
_PORT_VAR = "DIAGNOS_API_PORT"
_ALLOWED_CNS_VAR = "DIAGNOS_API_ALLOWED_CLIENT_CN"


class ApiConfigError(Exception):
    """The API's own configuration is missing or malformed; `main.run()` turns this into `sys.exit(2)`."""


def _require_tls_paths(source: Mapping[str, str]) -> tuple[str, str, str]:
    """Reads the three PEM paths that mTLS cannot start without, or raises naming exactly which are missing.

    mTLS is this API's *only* authentication (`CONVENTIONS.md`, `deploy/README.md`). There is no fallback mode that
    serves plain HTTP or accepts an unauthenticated client, so a missing CA or server keypair has to stop the process
    before it binds a socket instead of failing a request later with a confusing TLS error.
    """
    ca, cert, key = source.get(_CA_VAR), source.get(_CERT_VAR), source.get(_KEY_VAR)
    if not ca or not cert or not key:
        missing = [name for name, value in ((_CA_VAR, ca), (_CERT_VAR, cert), (_KEY_VAR, key)) if not value]
        joined = ", ".join(missing)
        raise ApiConfigError(
            f"missing required environment variable(s): {joined}. mTLS is this API's only "
            "authentication, so it refuses to start without a CA to verify client certificates and "
            "a certificate/key pair to serve HTTPS with. See apps/api/deploy/README.md."
        )
    return ca, cert, key


def _parse_port(raw: str | None) -> int:
    """Parses `DIAGNOS_API_PORT`, defaulting to `8443` (`deploy/README.md`)."""
    if not raw:
        return DEFAULT_PORT
    try:
        return int(raw)
    except ValueError as exc:
        raise ApiConfigError(f"{_PORT_VAR}={raw!r} is not a number.") from exc


def _parse_allowed_cns(raw: str | None) -> frozenset[str]:
    """Parses a CSV of client certificate common names, or returns an empty set (every CN) when unset."""
    if not raw:
        return frozenset()
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class ApiSettings:
    """Immutable configuration for the API process, built by `from_env`."""

    mtls_ca_file: str
    tls_cert_file: str
    tls_key_file: str
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    allowed_client_cns: frozenset[str] = frozenset()

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> ApiSettings:
        """Reads the environment table documented in `apps/api/deploy/README.md`.

        Args:
            env: The variables to read. Defaults to `os.environ`; an explicit mapping spares tests from monkeypatching
                process-global state, the same pattern `diagnos.Settings.from_env` uses.

        Returns:
            The validated settings.

        Raises:
            ApiConfigError: If a required TLS path is missing or `DIAGNOS_API_PORT` is not a number.
        """
        source = env if env is not None else os.environ
        ca, cert, key = _require_tls_paths(source)
        return ApiSettings(
            mtls_ca_file=ca,
            tls_cert_file=cert,
            tls_key_file=key,
            host=source.get(_HOST_VAR) or DEFAULT_HOST,
            port=_parse_port(source.get(_PORT_VAR)),
            allowed_client_cns=_parse_allowed_cns(source.get(_ALLOWED_CNS_VAR)),
        )
