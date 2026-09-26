"""🇺🇸 Decides, before any parsing, whether this command runs in the agent or in this process.

Commands that need the session go to the agent when one is running for
this identity; `login` starts one first. Everything else — `--help`,
`--version`, a plain `status`, or any command when the agent is off, absent
or unsupported — runs here, exactly as before the agent existed.

🇧🇷 Decide, antes de qualquer interpretação, se este comando roda no agente ou neste processo.

Os comandos que precisam da sessão vão para o agente quando há um rodando
para esta identidade; o `login` sobe um antes. Todo o resto — `--help`,
`--version`, um `status` simples, ou qualquer comando quando o agente está
desligado, ausente ou sem suporte — roda aqui, exatamente como antes do
agente existir.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from typing import IO, Any, Final

from .client import connect, ping, relay, start
from .paths import AgentUnavailable, agent_enabled, identity, idle_seconds, socket_path

_SESSION_COMMANDS: Final = frozenset({"login", "logout", "groups", "patients", "exams", "files", "session", "status"})
_VALUE_OPTIONS: Final = frozenset({"--token", "--vault-url"})


def _scan(argv: list[str]) -> tuple[str | None, str | None, str | None]:
    """🇺🇸 `(command, --token, --vault-url)` from global options already hoisted before the command.

    🇧🇷 `(comando, --token, --vault-url)` a partir das opções globais já içadas para antes do comando.
    """
    command = token = vault_url = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        name, has_value, value = arg.partition("=")
        if name in _VALUE_OPTIONS:
            if not has_value:
                index += 1
                value = argv[index] if index < len(argv) else ""
            token, vault_url = (value, vault_url) if name == "--token" else (token, value)
        elif arg == "--" or not arg.startswith("-"):
            command = None if arg == "--" else arg
            break
        index += 1
    return command, token, vault_url


def dispatch(
    argv: list[str],
    *,
    env: Mapping[str, str] = os.environ,
    stdin: IO[str] = sys.stdin,
    stdout: IO[str] = sys.stdout,
    stderr: IO[str] = sys.stderr,
) -> int | None:
    """🇺🇸 The command's exit code when the agent ran it; `None` means "run it here".

    🇧🇷 O código de saída do comando quando o agente o rodou; `None` significa "rode aqui".
    """
    if "--help" in argv or "--version" in argv:
        return None
    command, token, vault_url = _scan(argv)
    if command not in _SESSION_COMMANDS or not agent_enabled(env):
        return None
    if command == "status" and "--check" not in argv:
        return None
    who = identity(env, token, vault_url)
    if who is None:
        return None
    try:
        path = socket_path(env, who)
        conn = connect(path)
        if conn is None and command == "login":
            child_env = {**env, "DIAGNOS_VAULT_URL": who[0], "DIAGNOS_API_TOKEN": who[1]}
            start(path, child_env, idle_seconds=idle_seconds(env))
            conn = connect(path)
    except AgentUnavailable as exc:
        if command == "login":
            stderr.write(f"{exc}\n")
        return None
    if conn is None:
        return None
    with conn:
        return relay(conn, argv, env=env, stdin=stdin, stdout=stdout, stderr=stderr)


def agent_status(env: Mapping[str, str], token: str | None, vault_url: str | None) -> dict[str, Any] | None:
    """🇺🇸 The agent's status for this identity, for `diagnos status`; `None` when none is running.

    🇧🇷 O status do agente desta identidade, para o `diagnos status`; `None` quando não há um rodando.
    """
    who = identity(env, token, vault_url)
    if who is None or not agent_enabled(env):
        return None
    try:
        return ping(socket_path(env, who))
    except (AgentUnavailable, OSError):
        return None
