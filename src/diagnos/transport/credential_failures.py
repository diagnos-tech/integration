"""🇺🇸 The vault's `Credential*` error codes → typed exceptions whose message says exactly what to do.

The vault's own message says *what* happened; the SDK appends *what to do
about it*, because the person reading a traceback at 3 a.m. should not need
the docs open. Nothing here ever includes the seed, a signature or the token:
the inputs are the error envelope and the response headers, never the
request.

🇧🇷 Os códigos de erro `Credential*` do cofre → exceções tipadas cuja mensagem diz exatamente o que fazer.

A mensagem do próprio cofre diz *o que* aconteceu; o SDK acrescenta *o que
fazer*, porque quem lê um traceback às 3 da manhã não deveria precisar da doc
aberta. Nada aqui inclui a semente, uma assinatura ou um token: as entradas
são o envelope de erro e os headers da resposta, nunca a requisição.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Final

import httpx

from diagnos.errors import (
    ClockSkewError,
    CredentialError,
    CredentialExpiredError,
    CredentialReplayError,
    CredentialRevokedError,
    CredentialSignatureError,
    CredentialUnknownError,
    ScopeMissingError,
    WorkspaceMismatchError,
)

_PANEL: Final = "Settings → Service accounts · Configurações → Contas de serviço"
_REPLACE: Final = "`diagnos login` (or DIAGNOS_TOKEN · ou DIAGNOS_TOKEN)"
_HINTS: Final[dict[type[CredentialError], str]] = {
    CredentialSignatureError: (
        "🇺🇸 The signature did not verify (the vault checks both Ed25519 and ML-DSA-65): the token is not the one "
        "registered for this key, or something (a proxy) changed the request. Store the token again with "
        f"{_REPLACE}. "
        "🇧🇷 A assinatura não conferiu (o cofre confere Ed25519 e ML-DSA-65): o token não é o registrado para "
        f"esta chave, ou algo (um proxy) alterou a requisição. Guarde o token de novo com {_REPLACE}."
    ),
    CredentialReplayError: (
        "🇺🇸 The vault already saw this request's nonce: something resent it (a proxy or a retry outside the SDK). "
        "It was not retried, because the first copy may have gone through. "
        "🇧🇷 O cofre já viu o nonce desta requisição: algo a reenviou (um proxy ou uma retentativa fora do SDK). "
        "Não foi retentada, porque a primeira cópia pode ter passado."
    ),
    CredentialRevokedError: (
        f"🇺🇸 This token was revoked. Create a new token for the service account ({_PANEL}) and store it with "
        f"{_REPLACE}. "
        f"🇧🇷 Este token foi revogado. Crie um token novo para a conta de serviço ({_PANEL}) e guarde-o com "
        f"{_REPLACE}."
    ),
    CredentialExpiredError: (
        f"🇺🇸 This token reached its expiry date. Create a new token for the service account ({_PANEL}), store it "
        f"with {_REPLACE} and revoke the old one. 🇧🇷 Este token chegou à data de validade. Crie um token novo "
        f"para a conta de serviço ({_PANEL}), guarde-o com {_REPLACE} e revogue o antigo."
    ),
    CredentialUnknownError: (
        "🇺🇸 The vault does not know this token. Check DIAGNOS_VAULT_URL points at the environment where the "
        f"token was created; if it was deleted or revoked, create a new one ({_PANEL}). "
        "🇧🇷 O cofre não conhece este token. Confira se DIAGNOS_VAULT_URL aponta para o ambiente em que o token "
        f"foi criado; se ele foi apagado ou revogado, crie outro ({_PANEL})."
    ),
    WorkspaceMismatchError: (
        "🇺🇸 The token belongs to a different workspace than the one this request targets. Use a token created "
        "in the target workspace. "
        "🇧🇷 O token pertence a um workspace diferente do que esta requisição visa. Use um token criado no "
        "workspace de destino."
    ),
}
_CLASSES: Final[dict[str, type[CredentialError]]] = {
    "CredentialSignatureInvalid": CredentialSignatureError,
    "CredentialReplayed": CredentialReplayError,
    "CredentialClockSkew": ClockSkewError,
    "CredentialKeyRevoked": CredentialRevokedError,
    "CredentialKeyExpired": CredentialExpiredError,
    "CredentialKeyUnknown": CredentialUnknownError,
    "CredentialWorkspaceMismatch": WorkspaceMismatchError,
    "CredentialScopeMissing": ScopeMissingError,
}


def _instant(value: Any) -> datetime | None:
    """🇺🇸 `server_time` as Unix seconds, Unix milliseconds or ISO 8601. 🇧🇷 `server_time` em s, ms Unix ou ISO 8601."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        seconds = value / 1000 if value > 100_000_000_000 else value
        return datetime.fromtimestamp(seconds, UTC)
    if isinstance(value, str):
        try:
            return _instant(float(value))
        except ValueError:
            pass
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def server_time(details: dict[str, Any], response: httpx.Response) -> datetime | None:
    """🇺🇸 The vault's clock: `details.server_time` first, then the `Date` header.

    🇧🇷 O relógio do cofre: `details.server_time` primeiro, depois o header `Date`.
    """
    found = _instant(details.get("server_time"))
    if found is not None:
        return found
    date = response.headers.get("Date")
    try:
        return parsedate_to_datetime(date) if date else None
    except (TypeError, ValueError):
        return None


def _clock_hint(server: datetime | None, now: float) -> tuple[str, float | None]:
    """🇺🇸 The skew sentence and the skew in seconds. 🇧🇷 A frase da diferença e a diferença em segundos."""
    fix = (
        "Enable automatic time (NTP): Linux `sudo timedatectl set-ntp true`, macOS System Settings → General → "
        "Date & Time, Windows `w32tm /resync`; a container uses its host's clock. "
    )
    fix_pt = (
        "Ative a hora automática (NTP): Linux `sudo timedatectl set-ntp true`, macOS Ajustes → Geral → Data e "
        "Hora, Windows `w32tm /resync`; um container usa o relógio do host. "
    )
    if server is None:
        unknown = f"🇺🇸 This machine's clock is off by more than 60 s. {fix}"
        return f"{unknown}🇧🇷 O relógio desta máquina está fora por mais de 60 s. {fix_pt}", None
    skew = now - server.timestamp()
    side, side_pt = ("ahead of", "adiantado em relação a") if skew > 0 else ("behind", "atrasado em relação a")
    local = datetime.fromtimestamp(now, UTC).isoformat(timespec="seconds")
    vault = server.astimezone(UTC).isoformat(timespec="seconds")
    return (
        f"🇺🇸 This machine's clock is {abs(skew):.0f} s {side} the vault (here {local}, vault {vault}; the limit "
        f"is ±60 s). {fix}🇧🇷 O relógio desta máquina está {abs(skew):.0f} s {side_pt} o cofre (aqui {local}, cofre "
        f"{vault}; o limite é ±60 s). {fix_pt}"
    ), skew


def _scope_hint(details: dict[str, Any]) -> tuple[str, dict[str, str | None]]:
    """🇺🇸 The scope sentence and `resource`/`action`/`security_group_id`. 🇧🇷 A frase do escopo e os três campos."""
    fields: dict[str, str | None] = {
        name: value if isinstance(value := details.get(name), str) else None
        for name in ("resource", "action", "security_group_id")
    }
    resource, action, group = fields["resource"], fields["action"], fields["security_group_id"]
    if action and resource:
        what, what_pt = f"'{action}' on '{resource}'", f"'{action}' em '{resource}'"
    else:
        what = what_pt = f"'{action or resource}'" if action or resource else ""
    where = f" in security group '{group}'" if group else ""
    where_pt = f" no grupo de segurança '{group}'" if group else ""
    hint = (
        f"🇺🇸 This service account lacks the permission {what or '(unnamed)'}{where}. A token's scope is fixed when "
        f"it is created: ask a workspace admin for a new token with it ({_PANEL}). 🇧🇷 Falta à conta de serviço a "
        f"permissão {what_pt or '(sem nome)'}{where_pt}. O escopo de um token é fixado na criação: peça a um admin "
        f"do workspace um token novo com ela ({_PANEL})."
    )
    return hint, fields


def credential_error(
    code: str,
    message: str,
    *,
    response: httpx.Response,
    details: dict[str, Any],
    trace_id: str | None,
    now: float | None = None,
) -> CredentialError | None:
    """🇺🇸 The typed exception for a `Credential*` code, or `None` for any other code.

    🇧🇷 A exceção tipada para um código `Credential*`, ou `None` para qualquer outro código.
    """
    cls = _CLASSES.get(code)
    if cls is None:
        return None
    extra: dict[str, Any] = {}
    if cls is ClockSkewError:
        server = server_time(details, response)
        hint, skew = _clock_hint(server, time.time() if now is None else now)
        extra = {"skew_seconds": skew, "server_time": server}
    elif cls is ScopeMissingError:
        hint, fields = _scope_hint(details)
        extra = dict(fields)
    else:
        hint = _HINTS[cls]
    error = cls(
        code=code,
        message=f"{message} — {hint}" if message else hint,
        status=response.status_code,
        trace_id=trace_id,
        request_id=response.headers.get("X-Request-Id"),
        details=details,
    )
    for name, value in extra.items():
        setattr(error, name, value)
    return error
