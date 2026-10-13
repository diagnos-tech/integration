"""🇺🇸 Where an agent's socket lives, and the checks that keep that place private.

One agent per identity: the socket name is a hash of the vault URL and the
API token, so switching tokens reaches a different agent (or none) instead
of borrowing another account's session. The token itself is never written
anywhere — only a truncated SHA-256 of it names the socket.

🇧🇷 Onde fica o socket de um agente, e as checagens que mantêm esse lugar privado.

Um agente por identidade: o nome do socket é um hash da URL do cofre e do
token da API, então trocar de token chega a outro agente (ou a nenhum) em vez
de emprestar a sessão de outra conta. O token em si nunca é gravado em lugar
nenhum — só um SHA-256 truncado dele nomeia o socket.
"""

from __future__ import annotations

import hashlib
import os
import socket
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from diagnos import Settings

AGENT_ENV_VAR: Final = "DIAGNOS_AGENT"
IDLE_ENV_VAR: Final = "DIAGNOS_AGENT_IDLE_MINUTES"
DEFAULT_IDLE_MINUTES: Final = 8 * 60
_OFF_VALUES: Final = {"0", "off", "false", "no"}


class AgentUnavailable(Exception):  # noqa: N818 — a condition to fall back from, not an error to report
    """🇺🇸 The agent cannot be used here (platform, disabled, unsafe directory); commands run in-process.

    🇧🇷 O agente não pode ser usado aqui (plataforma, desligado, diretório inseguro); os comandos rodam no processo.
    """


def agent_enabled(env: Mapping[str, str]) -> bool:
    """🇺🇸 POSIX with Unix sockets, and not switched off with `DIAGNOS_AGENT=off`.

    🇧🇷 POSIX com sockets Unix, e não desligado com `DIAGNOS_AGENT=off`.
    """
    if os.name != "posix" or not hasattr(socket, "AF_UNIX"):
        return False
    return env.get(AGENT_ENV_VAR, "").strip().lower() not in _OFF_VALUES


def idle_seconds(env: Mapping[str, str]) -> float:
    """🇺🇸 `DIAGNOS_AGENT_IDLE_MINUTES` in seconds; a malformed or non-positive value keeps the default.

    🇧🇷 `DIAGNOS_AGENT_IDLE_MINUTES` em segundos; um valor malformado ou não positivo mantém o padrão.
    """
    try:
        minutes = float(env.get(IDLE_ENV_VAR, DEFAULT_IDLE_MINUTES))
    except ValueError:
        minutes = DEFAULT_IDLE_MINUTES
    return (minutes if minutes > 0 else DEFAULT_IDLE_MINUTES) * 60


def runtime_dir(env: Mapping[str, str]) -> Path:
    """🇺🇸 `$XDG_RUNTIME_DIR/diagnos-<uid>` (else the per-user temp dir), created `0700` and verified every time.

    A directory that another user owns or can enter is refused rather than
    repaired: someone else prepared it, and a socket inside it would be
    theirs to intercept.

    🇧🇷 `$XDG_RUNTIME_DIR/diagnos-<uid>` (senão o temp do usuário), criado `0700` e conferido toda vez.

    Um diretório de outro usuário, ou em que outro usuário entra, é recusado
    em vez de consertado: alguém o preparou, e um socket ali dentro seria
    dele para interceptar.
    """
    uid = os.getuid()
    base = Path(env.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
    directory = base / f"diagnos-{uid}"
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) & 0o077:
        raise AgentUnavailable(
            f"🇺🇸 {directory} must be a directory owned by you with mode 0700. "
            f"🇧🇷 {directory} precisa ser um diretório seu com modo 0700."
        )
    return directory


def identity(env: Mapping[str, str], token: str | None, vault_url: str | None) -> tuple[str, str] | None:
    """🇺🇸 The `(vault_url, api_token)` a command would use — flags over the environment; `None` without a token.

    🇧🇷 O `(vault_url, api_token)` que um comando usaria — flags acima do ambiente; `None` sem token.
    """
    api_token = token or env.get("DIAGNOS_API_TOKEN")
    if not api_token:
        return None
    return (vault_url or env.get("DIAGNOS_VAULT_URL") or Settings(api_token=api_token).vault_url), api_token


def socket_path(env: Mapping[str, str], who: tuple[str, str]) -> Path:
    """🇺🇸 The socket of the agent for `who` — named by a hash, never by the token.

    🇧🇷 O socket do agente de `who` — nomeado por um hash, nunca pelo token.
    """
    digest = hashlib.sha256("\n".join(who).encode("utf-8")).hexdigest()[:16]
    return runtime_dir(env) / f"agent-{digest}.sock"
