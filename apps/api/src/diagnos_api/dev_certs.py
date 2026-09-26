"""🇺🇸 `diagnos-api dev-certs`: a throwaway CA, a `localhost` server certificate and one client certificate.

mTLS is this API's only authentication, so even a laptop run needs a CA,
a server pair and a client pair. Five `openssl` invocations are where most
first attempts go wrong (a missing SAN, a key the CA did not sign); this
writes all three in one step. It is for local use only: the CA key sits
next to the certificates, every certificate lives 30 days, and a real
deployment uses the organization's own CA (`README.md`).

It needs `cryptography`, which is not a runtime dependency of the API: it
comes with the workspace's development install, or with
`pip install "diagnos-api[dev]"`.

🇧🇷 `diagnos-api dev-certs`: uma CA descartável, um certificado de servidor para `localhost` e um de cliente.

O mTLS é a única autenticação desta API, então até uma execução no notebook
precisa de uma CA, um par do servidor e um par de cliente. Cinco chamadas
de `openssl` são onde a maioria das primeiras tentativas erra (um SAN
faltando, uma chave que a CA não assinou); isto grava os três num passo. É
só para uso local: a chave da CA fica ao lado dos certificados, todo
certificado vive 30 dias, e um deployment de verdade usa a CA da própria
organização (`README.md`).

Precisa de `cryptography`, que não é dependência de runtime da API: vem com
a instalação de desenvolvimento do workspace, ou com
`pip install "diagnos-api[dev]"`.
"""

from __future__ import annotations

import os
from dataclasses import astuple, dataclass
from pathlib import Path
from typing import Final

VALID_DAYS: Final = 30
DEFAULT_CLIENT_CN: Final = "local-dev"


class DevCertsError(Exception):
    """🇺🇸 The certificates could not be written (files exist, `cryptography` missing).

    🇧🇷 Os certificados não puderam ser gravados (arquivos existem, `cryptography` ausente).
    """


@dataclass(frozen=True)
class DevCerts:
    """🇺🇸 Where each PEM was written. 🇧🇷 Onde cada PEM foi gravado."""

    ca: Path
    ca_key: Path
    server: Path
    server_key: Path
    client: Path
    client_key: Path

    @classmethod
    def under(cls, directory: Path) -> DevCerts:
        """🇺🇸 The fixed file names inside `directory`. 🇧🇷 Os nomes fixos de arquivo dentro de `directory`."""
        names = ("ca.pem", "ca-key.pem", "server.pem", "server-key.pem", "client.pem", "client-key.pem")
        return cls(*(directory / name for name in names))

    def environment(self) -> dict[str, str]:
        """🇺🇸 The variables that point the API at these files, bound to loopback.

        🇧🇷 As variáveis que apontam a API para estes arquivos, presa ao loopback.
        """
        return {
            "DIAGNOS_API_MTLS_CA_FILE": str(self.ca),
            "DIAGNOS_API_TLS_CERT_FILE": str(self.server),
            "DIAGNOS_API_TLS_KEY_FILE": str(self.server_key),
            "DIAGNOS_API_HOST": "127.0.0.1",
        }


def generate(directory: Path, *, client_cn: str = DEFAULT_CLIENT_CN, force: bool = False) -> DevCerts:
    """🇺🇸 Writes a CA, a server pair for `localhost`/`127.0.0.1`/`::1` and a client pair (CN `client_cn`).

    Keys are written `0600` in a `0700` directory; existing files are only
    replaced with `force`, so a second run never silently invalidates the
    client certificate someone already copied elsewhere.

    🇧🇷 Grava uma CA, um par do servidor para `localhost`/`127.0.0.1`/`::1` e um par de cliente (CN `client_cn`).

    As chaves são gravadas `0600` num diretório `0700`; arquivos existentes só
    são substituídos com `force`, para uma segunda execução nunca invalidar
    em silêncio o certificado de cliente que alguém já copiou para outro lugar.
    """
    try:
        from diagnos_api import _pki  # noqa: PLC0415 — optional dependency, only this command needs it
    except ImportError as exc:
        raise DevCertsError(
            '🇺🇸 dev-certs needs `cryptography`: pip install "diagnos-api[dev]". '
            '🇧🇷 o dev-certs precisa do `cryptography`: pip install "diagnos-api[dev]".'
        ) from exc
    paths = DevCerts.under(directory)
    existing = [str(path) for path in astuple(paths) if path.exists()]
    if existing and not force:
        raise DevCertsError(
            f"🇺🇸 already exists (pass --force to replace): {', '.join(existing)}. "
            f"🇧🇷 já existe (passe --force para substituir): {', '.join(existing)}."
        )
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
    """🇺🇸 Writes `data` into a file created with `mode` — a key is never world-readable, not even for an instant.

    🇧🇷 Grava `data` num arquivo criado já com `mode` — uma chave nunca fica legível por todos, nem por um instante.
    """
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
