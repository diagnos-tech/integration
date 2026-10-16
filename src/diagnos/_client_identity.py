"""🇺🇸 Which token `Diagnos` runs as: resolving it, warning about the legacy one, and the identity properties.

Kept apart from `client.py` so the client stays the wiring of layers; this
module is the one place that knows there are two kinds of token — the
service account token (`dgn_sk1_…`, classic + post-quantum) and the
deprecated `apikey-` one.

🇧🇷 Com qual token a `Diagnos` roda: resolvê-lo, avisar sobre o legado, e as propriedades de identidade.

Separado de `client.py` para o client continuar sendo a ligação das camadas;
este módulo é o único lugar que sabe que existem dois tipos de token — o
token de conta de serviço (`dgn_sk1_…`, clássico + pós-quântico) e o
`apikey-` obsoleto.
"""

from __future__ import annotations

import dataclasses
import logging
import sys
import warnings
from typing import TYPE_CHECKING, Literal

from diagnos._whoami import Whoami
from diagnos.errors import ConfigError
from diagnos.transport.config import Settings
from diagnos.transport.service_token import DiagnosToken
from diagnos.transport.token import ServiceAccountToken, redact_api_token
from diagnos.transport.token_sources import LEGACY_VAR, NOT_CONFIGURED, FoundIdentity, explicit
from diagnos.transport.token_text import LEGACY_SUNSET

if TYPE_CHECKING:
    from diagnos.session.keyring import Keyring

logger = logging.getLogger("diagnos")

TokenLike = DiagnosToken | str
"""🇺🇸 A parsed token, or its text (`dgn_sk1_…`, or the legacy `apikey-…`). 🇧🇷 Um token lido, ou o texto dele."""
Identity = DiagnosToken | ServiceAccountToken
_legacy_logged = False


class LegacyTokenWarning(DeprecationWarning):
    """🇺🇸 The `apikey-` token is deprecated; the vault stops accepting it on 2027-04-15.

    🇧🇷 O token `apikey-` está obsoleto; o cofre deixa de aceitá-lo em 2027-04-15.
    """


def resolve_settings(settings: Settings | None, token: TokenLike | None) -> Settings:
    """🇺🇸 An explicit service account token replaces the identity of `settings` or the environment.

    A legacy `apikey-` text next to explicit `settings` is ignored, exactly
    as before the token existed: there, `settings` always won.

    🇧🇷 Um token de conta de serviço explícito substitui a identidade de `settings` ou do ambiente.

    Um texto legado `apikey-` ao lado de `settings` explícitos é ignorado,
    exatamente como antes do token existir: ali, `settings` sempre venceu.
    """
    if settings is None:
        return Settings.from_env(token=token)
    if token is None or (isinstance(token, str) and token.lstrip().startswith("apikey-")):
        return settings
    try:
        found = FoundIdentity(token=token) if isinstance(token, DiagnosToken) else explicit(token, "token=")
    finally:
        # 🇺🇸 No frame of the SDK keeps the text past this point. 🇧🇷 Nenhum quadro do SDK guarda o texto daqui em diante.
        del token
    return dataclasses.replace(settings, token=found.token, api_token=found.api_token)


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
    """🇺🇸 The token if there is one; else the legacy `apikey-` token, with a `LegacyTokenWarning`.

    🇧🇷 O token se houver; senão o token legado `apikey-`, com um `LegacyTokenWarning`.
    """
    if settings.token is not None:
        return settings.token
    if not settings.api_token:
        raise ConfigError(NOT_CONFIGURED)
    token = ServiceAccountToken.parse(settings.api_token)
    message = (
        f"🇺🇸 {LEGACY_VAR} ('apikey-…') is deprecated and stops working on {LEGACY_SUNSET}. Create a service "
        "account token and run `diagnos login` (or set DIAGNOS_TOKEN): https://dev.diagnos.health/migrating "
        f"🇧🇷 {LEGACY_VAR} ('apikey-…') está obsoleto e deixa de funcionar em {LEGACY_SUNSET}. Crie um token "
        "de conta de serviço e rode `diagnos login` (ou defina DIAGNOS_TOKEN): https://dev.diagnos.health/migrating"
    )
    warnings.warn(message, LegacyTokenWarning, stacklevel=_outside_diagnos())
    global _legacy_logged  # noqa: PLW0603 — one log line per process, the warning filter handles the rest
    if not _legacy_logged:
        _legacy_logged = True
        logger.warning("%s (key %s)", message, redact_api_token(token.raw))
    return token


class IdentityView:
    """🇺🇸 The identity properties of `Diagnos`, read from whichever token it runs as.

    🇧🇷 As propriedades de identidade da `Diagnos`, lidas do token com que ela roda.
    """

    _identity: Identity

    def _keyring_provider(self) -> Keyring:
        """🇺🇸 The live keyring, unlocking on first use — `Diagnos` implements it. 🇧🇷 A `Diagnos` o implementa."""
        raise NotImplementedError

    def whoami(self) -> Whoami:
        """🇺🇸 Proves the token against the vault — a session opens only if both signatures verify — and says who it is.

        `diagnos login` calls this before storing a token: a revoked key, a
        wrong workspace or a skewed clock fails here, with the fix in the
        message, instead of on the first real command.

        🇧🇷 Prova o token contra o cofre — uma sessão só abre se as duas assinaturas conferirem — e diz quem ele é.

        O `diagnos login` chama isto antes de guardar um token: uma chave
        revogada, um workspace errado ou um relógio fora falham aqui, com a
        correção na mensagem, em vez de no primeiro comando de verdade.
        """
        keyring = self._keyring_provider()
        return Whoami(
            identity=self.identity,
            key_id=self.key_id,
            workspace_id=self.workspace_id,
            token_kind=self.token_kind,
            token_source=self.token_source,
            security_groups=keyring.security_group_ids,
            session_expires_at=keyring.session.expires_at,
        )

    @property
    def workspace_id(self) -> str:
        """🇺🇸 The workspace this token belongs to. 🇧🇷 O workspace a que este token pertence."""
        return self._identity.workspace_id

    @property
    def account_id(self) -> str | None:
        """🇺🇸 The legacy token's account id; `None` with a token, whose identity is the key itself.

        🇧🇷 O id de conta do token legado; `None` com um token, cuja identidade é a própria chave.
        """
        return self._identity.account_id if isinstance(self._identity, ServiceAccountToken) else None

    @property
    def name(self) -> str | None:
        """🇺🇸 The legacy token's account name (the slug); `None` with a token, which does not carry it.

        🇧🇷 O nome da conta do token legado (o slug); `None` com um token, que não o carrega.
        """
        if isinstance(self._identity, ServiceAccountToken):
            return self._identity.name.partition("@")[0]
        return None

    @property
    def email(self) -> str | None:
        """🇺🇸 `<name>@<workspace_id>.diagnos.health` of the legacy token; `None` without a name.

        🇧🇷 `<name>@<workspace_id>.diagnos.health` do token legado; `None` sem nome.
        """
        name = self.name
        return f"{name}@{self.workspace_id}.diagnos.health" if name else None

    @property
    def key_id(self) -> str:
        """🇺🇸 The key an admin rotates or revokes (`svc_<hex>` for a token). 🇧🇷 A chave que um admin gira ou revoga."""
        return self._identity.key_id

    @property
    def identity(self) -> str | None:
        """🇺🇸 `svc_<hex>@<workspace_id>.diagnos.health`; `None` with the legacy token.

        🇧🇷 `svc_<hex>@<workspace_id>.diagnos.health`; `None` com o token legado.
        """
        return self._identity.identity if isinstance(self._identity, DiagnosToken) else None

    @property
    def token_kind(self) -> Literal["hybrid", "legacy_apikey"]:
        """🇺🇸 `hybrid` (`dgn_sk1_…`) or the deprecated `legacy_apikey`. 🇧🇷 `hybrid` (`dgn_sk1_…`) ou o obsoleto."""
        return "hybrid" if isinstance(self._identity, DiagnosToken) else "legacy_apikey"

    @property
    def token_source(self) -> str:
        """🇺🇸 Where the token was read from: `DIAGNOS_TOKEN`, `keyring`, `OpenBao …`, `token=`.

        🇧🇷 De onde o token foi lido: `DIAGNOS_TOKEN`, `keyring`, `OpenBao …`, `token=`.
        """
        return self._identity.source if isinstance(self._identity, DiagnosToken) else LEGACY_VAR

    def _identity_repr(self) -> str:
        """🇺🇸 For `repr`: the identity, never a seed or a token.

        🇧🇷 Para `repr`: a identidade, nunca semente nem token.
        """
        if isinstance(self._identity, DiagnosToken):
            return f"identity={self._identity.identity!r}"
        return f"account_id={self._identity.account_id!r}, api_token={redact_api_token(self._identity.raw)!r}"
