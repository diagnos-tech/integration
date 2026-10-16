"""🇺🇸 Every exception the SDK raises, in one place.

Callers catch by class, never by message. `VaultError` carries the vault's
`code`, HTTP status and `trace_id` so a support ticket can find the event on
the server side; the subclasses map the codes documented in
`docs/PROTOCOL.md §12` to the decision the caller has to make (retry, wait,
buy credit, re-enroll, fix the input).

🇧🇷 Toda exceção que o SDK lança, num lugar só.

Quem chama captura por classe, nunca por mensagem. `VaultError` carrega o
`code` do cofre, o status HTTP e o `trace_id` para um chamado de suporte
achar o evento do lado do servidor; as subclasses mapeiam os códigos de
`docs/PROTOCOL.md §12` para a decisão que o chamador precisa tomar (tentar de
novo, esperar, comprar crédito, refazer o enrollment, corrigir a entrada).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class DiagnosError(Exception):
    """🇺🇸 Base of every SDK error. 🇧🇷 Base de todo erro do SDK."""


class ConfigError(DiagnosError):
    """🇺🇸 Missing or malformed configuration (env vars, token).

    🇧🇷 Configuração ausente ou malformada (variáveis de ambiente, token).
    """


class TokenError(ConfigError):
    """🇺🇸 The text given as the service account token is not one; the message says how to fix it.

    Raised before any network call, from the token's own CRC and format
    (spec §2): a token cut short or pasted with a character wrong says
    exactly that. Neither the message nor any attribute carries a byte of
    the text.

    🇧🇷 O texto dado como token de conta de serviço não é um; a mensagem diz como corrigir.

    Lançado antes de qualquer chamada de rede, pelo próprio CRC e formato do
    token (spec §2): um token cortado ou colado com um caractere errado diz
    exatamente isso. Nem a mensagem nem atributo algum carrega um byte do
    texto.
    """

    reason: str
    """🇺🇸 `prefix`, `encoding`, `length`, `checksum`, `workspace` or `empty` — branch on it, never on the message.

    🇧🇷 `prefix`, `encoding`, `length`, `checksum`, `workspace` ou `empty` — decida por ele, nunca pela mensagem.
    """
    source: str
    """🇺🇸 Where the text came from (`DIAGNOS_TOKEN`, `keyring`, …). 🇧🇷 De onde o texto veio."""

    def __init__(self, message: str, *, reason: str, source: str) -> None:
        """🇺🇸 `reason` is the machine code; `message` the fix. 🇧🇷 `reason` é o código; `message`, a correção."""
        super().__init__(message)
        self.reason = reason
        self.source = source


class TokenStoreError(ConfigError):
    """🇺🇸 There is nowhere safe to keep the token: no secure system keyring and no OpenBao configured.

    The token is never written to a text file, so the message lists the two
    places it can live, and `DIAGNOS_TOKEN` for CI and ephemeral containers.

    🇧🇷 Não há lugar seguro para guardar o token: sem chaveiro seguro do sistema e sem OpenBao configurado.

    O token nunca é gravado em arquivo de texto, então a mensagem lista os dois
    lugares em que ele pode morar, e o `DIAGNOS_TOKEN` para CI e containers
    efêmeros.
    """


class CryptoError(DiagnosError):
    """🇺🇸 An envelope did not open or a format did not match the protocol.

    Deliberately one class: distinguishing "wrong key" from "tampered
    ciphertext" would hand an oracle to whoever is probing.

    🇧🇷 Um envelope não abriu ou um formato não bateu com o protocolo.

    Uma classe só, de propósito: distinguir "chave errada" de "ciphertext
    adulterado" daria um oráculo a quem estiver sondando.
    """


class ProtocolError(DiagnosError):
    """🇺🇸 The vault answered something the protocol does not allow (e.g. signed a size that is not the body's).

    Not the caller's fault and not retryable: report it with the SDK
    version, or upgrade if the vault moved on.

    🇧🇷 O cofre respondeu algo que o protocolo não permite (ex.: assinou um tamanho que não é o do corpo).

    Não é culpa de quem chama e não adianta retentar: reporte com a versão
    do SDK, ou atualize se o cofre evoluiu.
    """


class VaultError(DiagnosError):
    """🇺🇸 The vault answered with an error envelope. 🇧🇷 O cofre respondeu com um envelope de erro."""

    code: str
    """🇺🇸 The vault's error code (`QuotaExceeded`, `DocumentNotFound`…) — branch on it, never on `message`.

    🇧🇷 O código de erro do cofre (`QuotaExceeded`, `DocumentNotFound`…) — decida por ele, nunca pela `message`.
    """
    message: str
    """🇺🇸 The vault's message, for a person. 🇧🇷 A mensagem do cofre, para uma pessoa."""
    status: int
    """🇺🇸 The HTTP status the vault answered with. 🇧🇷 O status HTTP com que o cofre respondeu."""
    trace_id: str | None
    """🇺🇸 The vault's trace id — what a support ticket needs to find the event.

    🇧🇷 O trace id do cofre — o que um chamado de suporte precisa para achar o evento.
    """
    request_id: str | None
    """🇺🇸 The `X-Request-Id` of the failed response. 🇧🇷 O `X-Request-Id` da resposta que falhou."""
    details: dict[str, Any]
    """🇺🇸 The error's `details` — data to recover with (`server_time`, the missing permission); often empty.

    🇧🇷 Os `details` do erro — dados para se recuperar (`server_time`, a permissão que falta); muitas vezes vazio.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        trace_id: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """🇺🇸 `code`/`status` decide the class; `trace_id`/`request_id` find the event server-side.

        🇧🇷 `code`/`status` decidem a classe; `trace_id`/`request_id` acham o evento no servidor.
        """
        super().__init__(f"{code} ({status}): {message}")
        self.code = code
        self.message = message
        self.status = status
        self.trace_id = trace_id
        self.request_id = request_id
        self.details = dict(details or {})


class ValidationError(VaultError):
    """🇺🇸 400/413 — the request itself is wrong; fix the input.

    🇧🇷 400/413 — a requisição está errada; corrija a entrada.
    """


class AuthenticationError(VaultError):
    """🇺🇸 401 — token, session or signature rejected; usually re-enroll.

    🇧🇷 401 — token, sessão ou assinatura recusados; em geral, refaça o enrollment.
    """


class QuotaError(VaultError):
    """🇺🇸 402 — the workspace has no credit for this; nothing was done.

    🇧🇷 402 — o workspace não tem crédito para isto; nada foi feito.
    """


class DiagnosPermissionError(VaultError):
    """🇺🇸 403 — the service account may not do this here.

    🇧🇷 403 — a service account não pode fazer isto aqui.
    """


class NotFoundError(VaultError):
    """🇺🇸 404. 🇧🇷 404."""


class ConflictError(VaultError):
    """🇺🇸 409 — state disagrees (pending version, replay).

    🇧🇷 409 — o estado discorda (versão pendente, replay).
    """


class RateLimitError(VaultError):
    """🇺🇸 429 — slow down; the SDK already retried with backoff.

    🇧🇷 429 — devagar; o SDK já tentou de novo com backoff.
    """


class CredentialError(VaultError):
    """🇺🇸 The vault refused the service account token itself (`Credential*` codes); the message says the fix.

    Catch this to handle every token failure at once; each subclass is also
    an `AuthenticationError` (401) or a `DiagnosPermissionError` (403).

    🇧🇷 O cofre recusou o próprio token da conta de serviço (códigos `Credential*`); a mensagem diz a correção.

    Capture esta para tratar toda falha do token de uma vez; cada subclasse
    também é `AuthenticationError` (401) ou `DiagnosPermissionError` (403).
    """


class CredentialSignatureError(CredentialError, AuthenticationError):
    """🇺🇸 `CredentialSignatureInvalid`: a half of the hybrid signature failed — wrong token, or the request changed.

    🇧🇷 `CredentialSignatureInvalid`: uma metade da assinatura híbrida falhou — token errado, ou a requisição mudou.
    """


class CredentialReplayError(CredentialError, AuthenticationError):
    """🇺🇸 `CredentialReplayed`: the vault already saw this nonce. 🇧🇷 O cofre já viu este nonce."""


class ClockSkewError(CredentialError, AuthenticationError):
    """🇺🇸 `CredentialClockSkew`: this machine's clock is outside the vault's ±60 s window.

    🇧🇷 `CredentialClockSkew`: o relógio desta máquina está fora da janela de ±60 s do cofre.
    """

    skew_seconds: float | None = None
    """🇺🇸 Local minus vault time, in seconds (positive: ahead); `None` if the vault sent no time.

    🇧🇷 Hora local menos a do cofre, em segundos (positivo: adiantado); `None` se o cofre não mandou a hora.
    """
    server_time: datetime | None = None
    """🇺🇸 The vault's time, from `server_time` or `Date`. 🇧🇷 A hora do cofre, de `server_time` ou `Date`."""


class CredentialRevokedError(CredentialError, AuthenticationError):
    """🇺🇸 `CredentialKeyRevoked`: an admin revoked this key. 🇧🇷 Um admin revogou esta chave."""


class CredentialExpiredError(CredentialError, AuthenticationError):
    """🇺🇸 `CredentialKeyExpired`: the key passed its expiry. 🇧🇷 A chave passou da validade."""


class CredentialUnknownError(CredentialError, AuthenticationError):
    """🇺🇸 `CredentialKeyUnknown`: the vault has no such key (mistyped, deleted, or another environment).

    🇧🇷 `CredentialKeyUnknown`: o cofre não tem esta chave (digitada errado, apagada, ou de outro ambiente).
    """


class WorkspaceMismatchError(CredentialError, DiagnosPermissionError):
    """🇺🇸 `CredentialWorkspaceMismatch`: the token belongs to another workspace.

    🇧🇷 `CredentialWorkspaceMismatch`: o token é de outro workspace.
    """


class ScopeMissingError(CredentialError, DiagnosPermissionError):
    """🇺🇸 `CredentialScopeMissing`: the service account lacks a permission. 🇧🇷 Falta uma permissão à conta."""

    resource: str | None = None
    """🇺🇸 The resource the permission is about (`details.resource`). 🇧🇷 O recurso da permissão (`details.resource`)."""
    action: str | None = None
    """🇺🇸 The missing action on it (`details.action`). 🇧🇷 A ação que falta sobre ele (`details.action`)."""
    security_group_id: str | None = None
    """🇺🇸 The group it is missing in, when named. 🇧🇷 O grupo em que ela falta, quando nomeado."""


class EnrollmentDeniedError(DiagnosError):
    """🇺🇸 A person denied this SDK session in the web app (legacy `apikey-` token only).

    🇧🇷 Uma pessoa negou esta sessão de SDK no app web (só o token legado `apikey-`).
    """


class EnrollmentExpiredError(DiagnosError):
    """🇺🇸 Nobody approved within the window; start again (legacy `apikey-` token only).

    🇧🇷 Ninguém aprovou dentro do prazo; comece de novo (só o token legado `apikey-`).
    """


class SessionExpiredError(DiagnosError):
    """🇺🇸 The session keys are past `expires_at`; `unlock()` opens a new one.

    🇧🇷 As chaves de sessão passaram de `expires_at`; `unlock()` abre uma nova.
    """
