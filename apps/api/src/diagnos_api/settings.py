"""🇺🇸 `ApiSettings`: everything the API process itself needs, read once from the environment.

This is deliberately separate from `diagnos.Settings` (the SDK's own
configuration): `ApiSettings` only knows about *this process's* HTTP/mTLS
concerns (which port to bind, which certificate pair to serve, which CA
signs the callers it trusts) and never touches the vault credential or
OpenBao configuration — those stay in `diagnos.Settings.from_env()`, read
independently wherever an `Diagnos` is constructed (`app.py`), so the two
configurations can never drift into reading the same variable two different
ways.

🇧🇷 `ApiSettings`: tudo que o próprio processo da API precisa, lido uma vez
do ambiente.

Isto é de propósito separado de `diagnos.Settings` (a configuração do
próprio SDK): `ApiSettings` só conhece as preocupações de HTTP/mTLS *deste
processo* (em qual porta escutar, qual par de certificado servir, qual CA
assina quem confia) e nunca toca a credencial do cofre nem a configuração do
OpenBao — isso fica em `diagnos.Settings.from_env()`, lido de forma
independente onde quer que um `Diagnos` seja construído (`app.py`), para as
duas configurações nunca divergirem lendo a mesma variável de dois jeitos.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

# 🇺🇸 `0.0.0.0` is the documented default (`deploy/README.md`) precisely
# because mTLS — not network placement — is what keeps this process safe to
# expose: every request is TLS-terminated here and rejected at the
# handshake without a client certificate the trusted CA signed, so binding
# every interface costs nothing a firewall wasn't already responsible for.
# 🇧🇷 `0.0.0.0` é o padrão documentado (`deploy/README.md`) exatamente porque
# é o mTLS — não a posição na rede — que mantém este processo seguro de
# expor: toda requisição termina TLS aqui e é recusada no handshake sem um
# certificado de cliente que a CA confiável assinou, então escutar em toda
# interface não custa nada que um firewall já não cobrisse.
DEFAULT_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_PORT = 8443

_CA_VAR = "DIAGNOS_API_MTLS_CA_FILE"
_CERT_VAR = "DIAGNOS_API_TLS_CERT_FILE"
_KEY_VAR = "DIAGNOS_API_TLS_KEY_FILE"
_HOST_VAR = "DIAGNOS_API_HOST"
_PORT_VAR = "DIAGNOS_API_PORT"
_ALLOWED_CNS_VAR = "DIAGNOS_API_ALLOWED_CLIENT_CN"


class ApiConfigError(Exception):
    """🇺🇸 The API's own configuration is missing or malformed; `main.run()` turns this into `sys.exit(2)`.

    🇧🇷 A configuração da própria API está ausente ou malformada; `main.run()` transforma isto em `sys.exit(2)`.
    """


def _require_tls_paths(source: Mapping[str, str]) -> tuple[str, str, str]:
    """🇺🇸 Reads the three PEM paths mTLS cannot start without, or raises naming exactly which are missing.

    mTLS is this API's *only* authentication (`CONVENTIONS.md`, `deploy/README.md`):
    there is no fallback mode that serves plain HTTP or accepts an
    unauthenticated client, so a missing CA or server keypair has to stop
    the process before it binds a socket, not fail a request later with a
    confusing TLS error.

    🇧🇷 Lê os três paths de PEM sem os quais o mTLS não sobe, ou lança
    nomeando exatamente quais estão faltando.

    mTLS é a *única* autenticação desta API (`CONVENTIONS.md`,
    `deploy/README.md`): não existe modo alternativo que sirva HTTP puro ou
    aceite um cliente sem autenticação, então uma CA ou par de chaves do
    servidor ausente precisa parar o processo antes de abrir um socket, não
    falhar uma requisição depois com um erro de TLS confuso.
    """
    ca, cert, key = source.get(_CA_VAR), source.get(_CERT_VAR), source.get(_KEY_VAR)
    if not ca or not cert or not key:
        missing = [name for name, value in ((_CA_VAR, ca), (_CERT_VAR, cert), (_KEY_VAR, key)) if not value]
        joined = ", ".join(missing)
        raise ApiConfigError(
            f"🇺🇸 missing required environment variable(s): {joined}. mTLS is this API's only "
            "authentication — it refuses to start without a CA to verify client certificates and "
            "a certificate/key pair to serve HTTPS with. See apps/api/deploy/README.md. "
            f"🇧🇷 variável(is) de ambiente obrigatória(s) ausente(s): {joined}. mTLS é a única "
            "autenticação desta API — ela se recusa a subir sem uma CA para verificar "
            "certificados de cliente e um par de certificado/chave para servir HTTPS. Veja "
            "apps/api/deploy/README.md."
        )
    return ca, cert, key


def _parse_port(raw: str | None) -> int:
    """🇺🇸 `DIAGNOS_API_PORT`, defaulting to `8443` (`deploy/README.md`).

    🇧🇷 `DIAGNOS_API_PORT`, com padrão `8443` (`deploy/README.md`).
    """
    if not raw:
        return DEFAULT_PORT
    try:
        return int(raw)
    except ValueError as exc:
        raise ApiConfigError(
            f"🇺🇸 {_PORT_VAR}={raw!r} is not a number. 🇧🇷 {_PORT_VAR}={raw!r} não é um número."
        ) from exc


def _parse_allowed_cns(raw: str | None) -> frozenset[str]:
    """🇺🇸 A CSV of client certificate common names, or every CN when unset (`deploy/README.md`).

    🇧🇷 Um CSV de common names de certificado de cliente, ou todo CN quando não definida
    (`deploy/README.md`).
    """
    if not raw:
        return frozenset()
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class ApiSettings:
    """🇺🇸 Immutable configuration for the API process, built by `from_env`.

    🇧🇷 Configuração imutável do processo da API, construída por `from_env`.
    """

    mtls_ca_file: str
    tls_cert_file: str
    tls_key_file: str
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    allowed_client_cns: frozenset[str] = frozenset()

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> ApiSettings:
        """🇺🇸 Reads the environment table documented in `apps/api/deploy/README.md`.

        `env` defaults to `os.environ` but accepts an explicit mapping so
        tests never have to monkeypatch process-global state — the same
        pattern `diagnos.Settings.from_env` uses.

        🇧🇷 Lê a tabela de ambiente documentada em `apps/api/deploy/README.md`.

        `env` usa `os.environ` por padrão, mas aceita um mapeamento
        explícito para os testes nunca precisarem de monkeypatch em estado
        global do processo — o mesmo padrão que `diagnos.Settings.from_env`
        usa.
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
