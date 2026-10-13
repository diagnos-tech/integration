"""🇺🇸 Maps every `DiagnosError` subclass the SDK can raise to a process exit code and a short bilingual label.

A script piping `diagnos` into `if`/`case` needs a stable, documented exit
code — never "1 for everything", which would force it to grep stderr text to
tell "not found" from "rate limited". This table is the single place that
mapping lives, so `main.py`'s wrapper stays a few lines and every command
gets identical behaviour for free.

🇧🇷 Mapeia toda subclasse de `DiagnosError` que o SDK pode lançar para um
código de saída de processo e um rótulo curto bilíngue.

Um script que encadeia `diagnos` num `if`/`case` precisa de um código de
saída estável e documentado — nunca "1 para tudo", o que o forçaria a fazer
grep no texto do stderr para distinguir "não encontrado" de "limite de
taxa". Esta tabela é o único lugar onde esse mapeamento mora, para o
wrapper do `main.py` ficar em poucas linhas e todo comando ganhar o mesmo
comportamento de graça.
"""

from __future__ import annotations

from diagnos import (
    AuthenticationError,
    ConfigError,
    ConflictError,
    DiagnosPermissionError,
    EnrollmentDeniedError,
    EnrollmentExpiredError,
    GroupKeyUnavailable,
    NotFoundError,
    QuotaError,
    RateLimitError,
    SessionExpiredError,
    ValidationError,
)

EXIT_OK = 0
EXIT_GENERAL = 1
EXIT_CONFIG = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
EXIT_QUOTA = 5
EXIT_RATE_LIMIT = 6
EXIT_CONFLICT = 7

# 🇺🇸 Checked in order with `isinstance`, most specific first — every entry
# here is a leaf of `DiagnosError` (`docs/PROTOCOL.md §12`); anything that
# does not match falls through to `EXIT_GENERAL` in `classify` below.
# `GroupKeyUnavailable` is a permission gap (the enrollment was never handed
# that group's key), so it shares the permission exit code.
# 🇧🇷 Conferido em ordem com `isinstance`, mais específico primeiro — toda
# entrada aqui é uma folha de `DiagnosError` (`docs/PROTOCOL.md §12`);
# o que não bater cai em `EXIT_GENERAL` em `classify` abaixo.
# `GroupKeyUnavailable` é uma lacuna de permissão (o enrollment nunca
# recebeu a chave daquele grupo), então divide o código de saída de
# permissão.
_RULES: tuple[tuple[type[Exception], int, str], ...] = (
    (ConfigError, EXIT_CONFIG, "Configuration error · Erro de configuração"),
    (AuthenticationError, EXIT_AUTH, "Authentication failed · Falha de autenticação"),
    (DiagnosPermissionError, EXIT_AUTH, "Permission denied · Permissão negada"),
    (GroupKeyUnavailable, EXIT_AUTH, "No key for this security group · Sem chave para este security group"),
    (SessionExpiredError, EXIT_AUTH, "Session expired · Sessão expirada"),
    (EnrollmentDeniedError, EXIT_AUTH, "Enrollment denied · Enrollment negado"),
    (EnrollmentExpiredError, EXIT_AUTH, "Enrollment expired · Enrollment expirado"),
    (NotFoundError, EXIT_NOT_FOUND, "Not found · Não encontrado"),
    (QuotaError, EXIT_QUOTA, "Quota exceeded · Cota excedida"),
    (RateLimitError, EXIT_RATE_LIMIT, "Rate limited · Limite de taxa excedido"),
    (ConflictError, EXIT_CONFLICT, "Conflict · Conflito"),
    (ValidationError, EXIT_GENERAL, "Invalid request · Requisição inválida"),
)


def classify(exc: Exception) -> tuple[int, str]:
    """🇺🇸 The `(exit_code, bilingual_label)` for `exc`; unmatched errors get `(EXIT_GENERAL, "Error · Erro")`.

    🇧🇷 O `(exit_code, rótulo_bilíngue)` de `exc`; erros não mapeados recebem `(EXIT_GENERAL, "Error · Erro")`.
    """
    for exc_type, code, label in _RULES:
        if isinstance(exc, exc_type):
            return code, label
    return EXIT_GENERAL, "Error · Erro"
