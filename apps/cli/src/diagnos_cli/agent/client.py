"""🇺🇸 The command side: reach the agent, hand it the command, replay its output, answer its prompts.

🇧🇷 O lado do comando: alcança o agente, entrega o comando, reproduz a saída, responde aos prompts.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any, Final

from . import protocol
from .paths import AgentUnavailable
from .server import FORWARDED_ENV

_START_TIMEOUT_SECONDS: Final = 10.0


def connect(path: Path) -> socket.socket | None:
    """🇺🇸 A connection to the agent at `path`, or `None` when no agent is listening there.

    🇧🇷 Uma conexão com o agente em `path`, ou `None` quando nenhum agente escuta ali.
    """
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        conn.connect(str(path))
    except (FileNotFoundError, ConnectionRefusedError):
        conn.close()
        return None
    return conn


def relay(
    conn: socket.socket,
    argv: list[str],
    *,
    env: Mapping[str, str],
    stdin: IO[str],
    stdout: IO[str],
    stderr: IO[str],
) -> int:
    """🇺🇸 Runs `argv` in the agent as if here: same directory, output and exit code; prompts read from `stdin`.

    🇧🇷 Roda `argv` no agente como se fosse aqui: mesmo diretório, saída e código de saída; prompts lidos de `stdin`.
    """
    forwarded = {key: env[key] for key in FORWARDED_ENV if key in env}
    if stdout.isatty() and "COLUMNS" not in forwarded:
        forwarded["COLUMNS"] = str(shutil.get_terminal_size().columns)
    protocol.send(
        conn,
        {
            "type": "run",
            "argv": argv,
            "cwd": os.getcwd(),
            "env": forwarded,
            "stdout_tty": stdout.isatty(),
            "stderr_tty": stderr.isatty(),
        },
    )
    reader = protocol.Reader(conn)
    while True:
        frame = reader.next()
        if frame is None:
            stderr.write("diagnos agent stopped mid-command · o agente do diagnos parou no meio do comando\n")
            return 1
        kind = frame["type"]
        if kind in ("out", "err"):
            stream = stdout if kind == "out" else stderr
            stream.write(str(frame.get("data", "")))
            stream.flush()
        elif kind == "prompt":
            protocol.send(conn, {"type": "input", "line": stdin.readline()})
        elif kind == "exit":
            return int(frame.get("code", 1))


def ping(path: Path) -> dict[str, Any] | None:
    """🇺🇸 The running agent's status, or `None` when there is none. 🇧🇷 O status do agente, ou `None` se não houver."""
    conn = connect(path)
    if conn is None:
        return None
    with conn:
        protocol.send(conn, {"type": "ping"})
        return protocol.Reader(conn).next()


def start(path: Path, env: Mapping[str, str], *, idle_seconds: float) -> None:
    """🇺🇸 Starts a detached agent for `path` and waits until it listens.

    The agent gets its own session (`start_new_session`), so closing this
    terminal does not take it down, and `/dev/null` for stdio: everything it
    prints goes to the command that asked, over the socket.

    🇧🇷 Sobe um agente destacado para `path` e espera até ele escutar.

    O agente ganha a própria sessão (`start_new_session`), então fechar este
    terminal não o derruba, e `/dev/null` como stdio: tudo o que ele imprime
    vai para o comando que pediu, pelo socket.
    """
    command = [sys.executable, "-m", "diagnos_cli.agent", "--socket", str(path), "--idle", str(idle_seconds)]
    subprocess.Popen(  # noqa: S603 — our own interpreter and module, no shell, no user-controlled argv
        command,
        env=dict(env),
        cwd="/",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    deadline = time.monotonic() + _START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        conn = connect(path)
        if conn is not None:
            conn.close()
            return
        time.sleep(0.05)
    raise AgentUnavailable("🇺🇸 the diagnos agent did not start in time. 🇧🇷 o agente do diagnos não subiu a tempo.")
