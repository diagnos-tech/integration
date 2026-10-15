"""🇺🇸 Which credential `Diagnos` runs as: resolving it, warning about the legacy token, and the identity properties.

Kept apart from `client.py` so the client stays the wiring of layers; this
module is the one place that knows there are two kinds of credential — the
Ed25519 service account credential and the deprecated `apikey-` token.

🇧🇷 Com qual credencial a `Diagnos` roda: resolvê-la, avisar sobre o token legado, e as propriedades de identidade.

Separado de `client.py` para o client continuar sendo a ligação das camadas;
este módulo é o único lugar que sabe que existem dois tipos de credencial — a
credencial Ed25519 de conta de serviço e o token `apikey-` obsoleto.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import sys
import warnings
from typing import Final, Literal

from diagnos.errors import ConfigError
from diagnos.transport.config import Settings
from diagnos.transport.credential import NOT_CONFIGURED, ServiceAccountCredential, mask_identity
from diagnos.transport.token import ServiceAccountToken, redact_api_token

logger = logging.getLogger("diagnos")

CredentialLike = ServiceAccountCredential | str | os.PathLike[str]
"""🇺🇸 A credential, its one-line form, or its JSON file. 🇧🇷 Uma credencial, sua linha, ou seu arquivo JSON."""
Identity = ServiceAccountCredential | ServiceAccountToken
LEGACY_SUNSET: Final = "2027-04-15"
_legacy_logged = False


class LegacyTokenWarning(DeprecationWarning):
    """🇺🇸 The `apikey-` token is deprecated; the vault stops accepting it on 2027-04-15.

    🇧🇷 O token `apikey-` está obsoleto; o cofre deixa de aceitá-lo em 2027-04-15.
    """


def as_credential(value: CredentialLike) -> ServiceAccountCredential:
    """🇺🇸 A `str` is the one-line form; a path is the JSON file. 🇧🇷 Uma `str` é a linha; um caminho é o arquivo JSON."""
    if isinstance(value, ServiceAccountCredential):
        return value
    if isinstance(value, str):
        return ServiceAccountCredential.parse(value, source="credential= · credencial=")
    return ServiceAccountCredential.from_file(value)


def resolve_settings(settings: Settings | None, token: str | None, credential: CredentialLike | None) -> Settings:
    """🇺🇸 Explicit arguments over the environment: `credential`, then `token`, then discovery.

    An explicit `token` hides `DIAGNOS_CREDENTIAL`/`DIAGNOS_CREDENTIALS_FILE`
    from discovery, so the argument a caller typed always wins.

    🇧🇷 Argumentos explícitos acima do ambiente: `credential`, depois `token`, depois a descoberta.

    Um `token` explícito esconde `DIAGNOS_CREDENTIAL`/`DIAGNOS_CREDENTIALS_FILE`
    da descoberta, para o argumento que quem chama digitou sempre vencer.
    """
    explicit = as_credential(credential) if credential is not None else None
    if settings is not None:
        return dataclasses.replace(settings, credential=explicit) if explicit is not None else settings
    if explicit is not None:
        return Settings.from_env(credential=explicit)
    if token is not None:
        hidden = {"DIAGNOS_CREDENTIAL", "DIAGNOS_CREDENTIALS_FILE"}
        env = {key: value for key, value in os.environ.items() if key not in hidden}
        return Settings.from_env({**env, "DIAGNOS_API_TOKEN": token})
    return Settings.from_env()


def _outside_diagnos() -> int:
    """🇺🇸 The `stacklevel` of the first frame outside the `diagnos` package — the caller's own line.

    A `DeprecationWarning` is shown by default only when attributed to
    `__main__`; pointing it at the SDK's internals would hide it.

    🇧🇷 O `stacklevel` do primeiro quadro fora do pacote `diagnos` — a própria linha de quem chamou.

    Um `DeprecationWarning` só aparece por padrão quando atribuído ao
    `__main__`; apontá-lo para o interior do SDK o esconderia.
    """
    frame = sys._getframe(1)  # noqa: SLF001 — the documented way to walk the stack cheaply
    level = 1
    while frame.f_back is not None and str(frame.f_globals.get("__name__", "")).partition(".")[0] == "diagnos":
        frame = frame.f_back
        level += 1
    return level


def resolve_identity(settings: Settings) -> Identity:
    """🇺🇸 The credential if there is one; else the legacy token, with a `LegacyTokenWarning`.

    🇧🇷 A credencial se houver; senão o token legado, com um `LegacyTokenWarning`.
    """
    if settings.credential is not None:
        return settings.credential
    if not settings.api_token:
        raise ConfigError(NOT_CONFIGURED)
    token = ServiceAccountToken.parse(settings.api_token)
    message = (
        f"🇺🇸 DIAGNOS_API_TOKEN ('apikey-…') is deprecated and stops working on {LEGACY_SUNSET}. Create a "
        "service account credential and set DIAGNOS_CREDENTIAL instead: https://dev.diagnos.health/migrating "
        f"🇧🇷 DIAGNOS_API_TOKEN ('apikey-…') está obsoleto e deixa de funcionar em {LEGACY_SUNSET}. Crie uma "
        "credencial de conta de serviço e use DIAGNOS_CREDENTIAL: https://dev.diagnos.health/migrating"
    )
    warnings.warn(message, LegacyTokenWarning, stacklevel=_outside_diagnos())
    global _legacy_logged  # noqa: PLW0603 — one log line per process, the warning filter handles the rest
    if not _legacy_logged:
        _legacy_logged = True
        logger.warning("%s (key %s)", message, redact_api_token(token.raw))
    return token


class IdentityView:
    """🇺🇸 The identity properties of `Diagnos`, read from whichever credential it runs as.

    🇧🇷 As propriedades de identidade da `Diagnos`, lidas da credencial com que ela roda.
    """

    _identity: Identity

    @property
    def workspace_id(self) -> str:
        """🇺🇸 The workspace this credential belongs to. 🇧🇷 O workspace a que esta credencial pertence."""
        return self._identity.workspace_id

    @property
    def account_id(self) -> str | None:
        """🇺🇸 The legacy token's account id; `None` with a credential, whose identity is the key itself.

        🇧🇷 O id de conta do token legado; `None` com uma credencial, cuja identidade é a própria chave.
        """
        return self._identity.account_id if isinstance(self._identity, ServiceAccountToken) else None

    @property
    def name(self) -> str | None:
        """🇺🇸 The service account's short name (the slug); `None` when only the one-line credential is known.

        🇧🇷 O nome curto da conta de serviço (o slug); `None` quando só a credencial de uma linha é conhecida.
        """
        if isinstance(self._identity, ServiceAccountToken):
            return self._identity.name.partition("@")[0]
        account = self._identity.service_account
        return account.partition("@")[0] if account else None

    @property
    def email(self) -> str | None:
        """🇺🇸 The account's full address, `<name>@<workspace_id>.diagnos.health`; `None` without a name.

        🇧🇷 O endereço completo da conta, `<name>@<workspace_id>.diagnos.health`; `None` sem nome.
        """
        name = self.name
        return f"{name}@{self.workspace_id}.diagnos.health" if name else None

    @property
    def key_id(self) -> str:
        """🇺🇸 The key an admin rotates or revokes. 🇧🇷 A chave que um admin gira ou revoga."""
        return self._identity.key_id

    @property
    def identity(self) -> str | None:
        """🇺🇸 `svc_<hex>@<workspace_id>.diagnos.health`; `None` with the legacy token.

        🇧🇷 `svc_<hex>@<workspace_id>.diagnos.health`; `None` com o token legado.
        """
        return self._identity.identity if isinstance(self._identity, ServiceAccountCredential) else None

    @property
    def credential_kind(self) -> Literal["ed25519", "legacy_apikey"]:
        """🇺🇸 Which kind of credential this client runs as. 🇧🇷 Com que tipo de credencial este client roda."""
        return "ed25519" if isinstance(self._identity, ServiceAccountCredential) else "legacy_apikey"

    def _identity_repr(self) -> str:
        """🇺🇸 Masked, for `repr`: never a seed or a token. 🇧🇷 Mascarado, para `repr`: nunca semente nem token."""
        if isinstance(self._identity, ServiceAccountCredential):
            return f"credential={mask_identity(self._identity.identity)!r}"
        return f"account_id={self._identity.account_id!r}, api_token={redact_api_token(self._identity.raw)!r}"
