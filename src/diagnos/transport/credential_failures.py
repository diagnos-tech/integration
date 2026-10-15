"""🇺🇸 The vault's `credential_*` error codes → typed exceptions whose message says exactly what to do.

The vault's own message says *what* happened; the SDK appends *what to do
about it*, because the person reading a traceback at 3 a.m. should not need
the docs open. Nothing here ever includes the seed, a signature or a token:
the inputs are the error envelope and the response headers, never the
request.

🇧🇷 Os códigos de erro `credential_*` do cofre → exceções tipadas cuja mensagem diz exatamente o que fazer.

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
_REPLACE: Final = "DIAGNOS_CREDENTIAL / DIAGNOS_CREDENTIALS_FILE"
_HINTS: Final[dict[type[CredentialError], str]] = {
    CredentialSignatureError: (
        "🇺🇸 The signature did not verify: the credential is not the one registered for this key, or something "
        f"(a proxy) changed the request. Copy the credential again from where you saved it into {_REPLACE}. "
        "🇧🇷 A assinatura não conferiu: a credencial não é a registrada para esta chave, ou algo (um proxy) "
        f"alterou a requisição. Copie de novo a credencial de onde você a guardou para {_REPLACE}."
    ),
    CredentialReplayError: (
        "🇺🇸 The vault already saw this request's nonce: something resent it (a proxy or a retry outside the SDK). "
        "It was not retried, because the first copy may have gone through. "
        "🇧🇷 O cofre já viu o nonce desta requisição: algo a reenviou (um proxy ou uma retentativa fora do SDK). "
        "Não foi retentada, porque a primeira cópia pode ter passado."
    ),
    CredentialRevokedError: (
        f"🇺🇸 This key was revoked. Create a new key for the service account ({_PANEL} → Rotate key) and put "
        f"it in {_REPLACE}. 🇧🇷 Esta chave foi revogada. Crie uma chave nova para a conta de serviço ({_PANEL} "
        f"→ Girar chave) e coloque-a em {_REPLACE}."
    ),
    CredentialExpiredError: (
        f"🇺🇸 This key reached its expiry date. Create a new key ({_PANEL} → Rotate key) and put it in "
        f"{_REPLACE}. 🇧🇷 Esta chave chegou à data de validade. Crie uma chave nova ({_PANEL} → Girar chave) e "
        f"coloque-a em {_REPLACE}."
    ),
    CredentialUnknownError: (
        "🇺🇸 The vault does not know this key. Check DIAGNOS_VAULT_URL points at the environment where the "
        f"credential was created; if the key was deleted or revoked, create a new one ({_PANEL}). "
        "🇧🇷 O cofre não conhece esta chave. Confira se DIAGNOS_VAULT_URL aponta para o ambiente em que a "
        f"credencial foi criada; se a chave foi apagada ou revogada, crie outra ({_PANEL})."
    ),
    WorkspaceMismatchError: (
        "🇺🇸 The credential belongs to a different workspace than the one this request targets. Use a credential "
        "created in the target workspace. "
        "🇧🇷 A credencial pertence a um workspace diferente do que esta requisição visa. Use uma credencial "
        "criada no workspace de destino."
    ),
}
_CLASSES: Final[dict[str, type[CredentialError]]] = {
    "credential_signature_invalid": CredentialSignatureError,
    "credential_replayed": CredentialReplayError,
    "credential_clock_skew": ClockSkewError,
    "credential_key_revoked": CredentialRevokedError,
    "credential_key_expired": CredentialExpiredError,
    "credential_key_unknown": CredentialUnknownError,
    "credential_workspace_mismatch": WorkspaceMismatchError,
    "credential_scope_missing": ScopeMissingError,
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


def _scope_hint(details: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """🇺🇸 The scope sentence, the permission and the group. 🇧🇷 A frase do escopo, a permissão e o grupo."""
    permission = details.get("permission")
    group = details.get("security_group_id", details.get("group"))
    what = f"'{permission}'" if isinstance(permission, str) else "a permission · uma permissão"
    where = f" in security group '{group}'" if isinstance(group, str) else ""
    where_pt = f" no grupo de segurança '{group}'" if isinstance(group, str) else ""
    hint = (
        f"🇺🇸 This service account lacks {what}{where}. Ask a workspace admin to grant it ({_PANEL}). "
        f"🇧🇷 Falta {what} a esta conta de serviço{where_pt}. Peça a um admin do workspace para concedê-la ({_PANEL})."
    )
    return hint, permission if isinstance(permission, str) else None, group if isinstance(group, str) else None


def credential_error(
    code: str,
    message: str,
    *,
    response: httpx.Response,
    details: dict[str, Any],
    trace_id: str | None,
    now: float | None = None,
) -> CredentialError | None:
    """🇺🇸 The typed exception for a `credential_*` code, or `None` for any other code.

    🇧🇷 A exceção tipada para um código `credential_*`, ou `None` para qualquer outro código.
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
        hint, permission, group = _scope_hint(details)
        extra = {"permission": permission, "security_group_id": group}
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
