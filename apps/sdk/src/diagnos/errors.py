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


class DiagnosError(Exception):
    """🇺🇸 Base of every SDK error. 🇧🇷 Base de todo erro do SDK."""


class ConfigError(DiagnosError):
    """🇺🇸 Missing or malformed configuration (env vars, token).

    🇧🇷 Configuração ausente ou malformada (variáveis de ambiente, token).
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

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        trace_id: str | None = None,
        request_id: str | None = None,
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


class EnrollmentDeniedError(DiagnosError):
    """🇺🇸 A person denied this SDK session in the web app.

    🇧🇷 Uma pessoa negou esta sessão de SDK no app web.
    """


class EnrollmentExpiredError(DiagnosError):
    """🇺🇸 Nobody approved within the window; start again.

    🇧🇷 Ninguém aprovou dentro do prazo; comece de novo.
    """


class SessionExpiredError(DiagnosError):
    """🇺🇸 The session keys are past `expires_at`; enroll again.

    🇧🇷 As chaves de sessão passaram de `expires_at`; refaça o enrollment.
    """
