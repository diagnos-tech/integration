"""`diagnos-api dev-certs`: a throwaway CA, a `localhost` server certificate and one client certificate.

mTLS is this API's only authentication, so even a laptop run needs a CA, a server pair and a client pair. Five
`openssl` invocations are where most first attempts go wrong (a missing SAN, a key the CA did not sign); this module
writes all three in one step. It is for local use only: the CA key sits next to the certificates, every certificate
lives 30 days, and a real deployment uses the organization's own CA (`README.md`).

It needs `cryptography`, which is not a runtime dependency of the API: it comes with the development install
(`uv sync`), or with `pip install "diagnos[dev-certs]"`.
"""

from __future__ import annotations

import os
from dataclasses import astuple, dataclass
from pathlib import Path
from typing import Final

VALID_DAYS: Final = 30
DEFAULT_CLIENT_CN: Final = "local-dev"


class DevCertsError(Exception):
    """The certificates could not be written (files exist, `cryptography` missing)."""


@dataclass(frozen=True)
class DevCerts:
    """Where each PEM was written."""

    ca: Path
    ca_key: Path
    server: Path
    server_key: Path
    client: Path
    client_key: Path

    @classmethod
    def under(cls, directory: Path) -> DevCerts:
        """Returns the fixed file names inside `directory`."""
        names = ("ca.pem", "ca-key.pem", "server.pem", "server-key.pem", "client.pem", "client-key.pem")
        return cls(*(directory / name for name in names))

    def environment(self) -> dict[str, str]:
        """Returns the variables that point the API at these files, bound to loopback."""
        return {
            "DIAGNOS_API_MTLS_CA_FILE": str(self.ca),
            "DIAGNOS_API_TLS_CERT_FILE": str(self.server),
            "DIAGNOS_API_TLS_KEY_FILE": str(self.server_key),
            "DIAGNOS_API_HOST": "127.0.0.1",
        }


def generate(directory: Path, *, client_cn: str = DEFAULT_CLIENT_CN, force: bool = False) -> DevCerts:
    """Writes a CA, a server pair for `localhost`/`127.0.0.1`/`::1` and a client pair (CN `client_cn`).

    Keys are written `0600` in a `0700` directory. Existing files are replaced only with `force`, so a second run never
    silently invalidates a client certificate that someone already copied elsewhere.

    Args:
        directory: Where to write the six PEM files; created with mode `0700` if missing.
        client_cn: The common name of the client certificate, which `DIAGNOS_API_ALLOWED_CLIENT_CN` matches.
        force: Replace files that already exist instead of refusing.

    Returns:
        The path of every file written.

    Raises:
        DevCertsError: If `cryptography` is not installed, or a target file exists and `force` is false.
    """
    try:
        from diagnos.api import _pki  # noqa: PLC0415 — optional dependency, only this command needs it
    except ImportError as exc:
        raise DevCertsError('dev-certs needs `cryptography`: pip install "diagnos[dev-certs]".') from exc
    paths = DevCerts.under(directory)
    existing = [str(path) for path in astuple(paths) if path.exists()]
    if existing and not force:
        raise DevCertsError(f"already exists (pass --force to replace): {', '.join(existing)}.")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    ca = _pki.issue_ca("diagnos-api local dev CA", days=VALID_DAYS)
    issued = [
        (paths.ca, paths.ca_key, ca),
        (paths.server, paths.server_key, _pki.issue_server(ca, days=VALID_DAYS)),
        (paths.client, paths.client_key, _pki.issue_client(ca, client_cn, days=VALID_DAYS)),
    ]
    for certificate_path, key_path, (key, certificate) in issued:
        _write(certificate_path, _pki.certificate_pem(certificate), mode=0o644)
        _write(key_path, _pki.key_pem(key), mode=0o600)
    return paths


def _write(path: Path, data: bytes, *, mode: int) -> None:
    """Writes `data` into a file created with `mode`, so a key is never world-readable, not even for an instant."""
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
