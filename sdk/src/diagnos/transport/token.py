"""🇺🇸 `DIAGNOS_API_TOKEN` parsing — the SDK's own identity, not the vault's.

The token is `apikey-<JWT EdDSA>`. The SDK never verifies the signature: it
has no business doing so, because the vault is the only party that can (it
holds the workspace's signing key, and revocation is server-side). All the
SDK needs from the JWT is `workspace_id`, to build the URLs every resource
call targets, so this module just decodes the payload as opaque JSON and
checks the claims it depends on are there.

🇧🇷 Leitura de `DIAGNOS_API_TOKEN` — a identidade do SDK, não a do cofre.

O token é `apikey-<JWT EdDSA>`. O SDK nunca verifica a assinatura: não é
função dele fazer isso, porque só o cofre pode (é quem guarda a chave de
assinatura do workspace, e revogação é do lado do servidor). Tudo que o SDK
precisa do JWT é `workspace_id`, para montar as URLs de toda chamada de
recurso, então este módulo só decodifica o payload como JSON opaco e confere
se as claims de que depende estão lá.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from diagnos.crypto.encoding import b64url_decode
from diagnos.errors import ConfigError

_PREFIX = "apikey-"
_REQUIRED_CLAIMS = ("sub", "account_id", "workspace_id", "name")


def redact_api_token(token: str) -> str:
    """🇺🇸 `apikey-<jwt>` becomes `apikey-…<last 4 chars>` for logs and `repr`.

    Enough to tell two tokens apart (or confirm one didn't change) without
    ever printing bytes that grant API access.

    🇧🇷 `apikey-<jwt>` vira `apikey-…<últimos 4 chars>` para log e `repr`.

    Basta para diferenciar dois tokens (ou confirmar que um não mudou) sem
    nunca imprimir bytes que dão acesso à API.
    """
    tail = token[-4:] if len(token) >= 4 else token
    return f"{_PREFIX}…{tail}"


@dataclass(frozen=True)
class ServiceAccountToken:
    """🇺🇸 The decoded shape of `DIAGNOS_API_TOKEN`, unsigned-checked on purpose.

    🇧🇷 A forma decodificada de `DIAGNOS_API_TOKEN`, propositalmente sem
    conferir a assinatura.
    """

    raw: str
    key_id: str
    account_id: str
    workspace_id: str
    name: str

    @classmethod
    def parse(cls, raw: str) -> ServiceAccountToken:
        """🇺🇸 Decode `apikey-<jwt>` into its claims, no signature check.

        A missing prefix or claim is a configuration mistake the caller can
        fix (wrong env var, copy-pasted the wrong secret) — `ConfigError`,
        not `CryptoError`, which is reserved for envelopes that should have
        opened and did not.

        🇧🇷 Decodifica `apikey-<jwt>` nas claims, sem conferir assinatura.

        Prefixo ou claim ausente é erro de configuração que o chamador
        corrige (env var errada, segredo colado errado) — `ConfigError`, não
        `CryptoError`, reservado a envelope que deveria abrir e não abriu.
        """
        if not raw.startswith(_PREFIX):
            raise ConfigError(
                "🇺🇸 DIAGNOS_API_TOKEN must start with 'apikey-'; check you copied the "
                "full service account token from the vault. "
                "🇧🇷 DIAGNOS_API_TOKEN precisa começar com 'apikey-'; confira se você "
                "copiou o token de service account inteiro do cofre."
            )
        jwt = raw[len(_PREFIX) :]
        segments = jwt.split(".")
        if len(segments) != 3:
            raise ConfigError(
                "🇺🇸 DIAGNOS_API_TOKEN does not carry a JWT with three segments "
                "(header.payload.signature); the token looks truncated or corrupted. "
                "🇧🇷 DIAGNOS_API_TOKEN não carrega um JWT de três segmentos "
                "(header.payload.signature); o token parece truncado ou corrompido."
            )
        try:
            payload = json.loads(b64url_decode(segments[1]))
        except Exception as exc:
            raise ConfigError(
                "🇺🇸 DIAGNOS_API_TOKEN's JWT payload is not valid base64url JSON. "
                "🇧🇷 O payload do JWT de DIAGNOS_API_TOKEN não é JSON base64url válido."
            ) from exc
        if not isinstance(payload, dict):
            raise ConfigError(
                "🇺🇸 DIAGNOS_API_TOKEN's JWT payload must be a JSON object. "
                "🇧🇷 O payload do JWT de DIAGNOS_API_TOKEN precisa ser um objeto JSON."
            )
        missing = [claim for claim in _REQUIRED_CLAIMS if claim not in payload]
        if missing:
            raise ConfigError(
                f"🇺🇸 DIAGNOS_API_TOKEN's JWT is missing claim(s) {missing}; it was not "
                "issued the way the vault issues service account tokens. "
                f"🇧🇷 O JWT de DIAGNOS_API_TOKEN está sem a(s) claim(s) {missing}; não foi "
                "emitido do jeito que o cofre emite tokens de service account."
            )
        return cls(
            raw=raw,
            key_id=str(payload["sub"]),
            account_id=str(payload["account_id"]),
            workspace_id=str(payload["workspace_id"]),
            name=str(payload["name"]),
        )

    def authorization_header(self) -> dict[str, str]:
        """🇺🇸 The one header every request needs, signed or not.

        🇧🇷 O único header que toda requisição precisa, assinada ou não.
        """
        return {"Authorization": f"Bearer {self.raw}"}

    def __repr__(self) -> str:
        """🇺🇸 Redacted: this repr ends up in logs and tracebacks. 🇧🇷 Redigido: este repr acaba em log e traceback."""
        return (
            f"ServiceAccountToken(key_id={self.key_id!r}, account_id={self.account_id!r}, "
            f"workspace_id={self.workspace_id!r}, name={self.name!r}, raw={redact_api_token(self.raw)!r})"
        )
