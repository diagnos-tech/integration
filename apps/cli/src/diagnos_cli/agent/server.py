"""🇺🇸 The agent process: accept one command at a time, run it against the one kept session, stream it back.

Commands run one after another, never concurrently: `sys.stdout`,
`sys.stdin` and the working directory are process-wide, and a CLI user
typing two commands does not need them interleaved. A second client simply
waits in the listen queue.

🇧🇷 O processo agente: aceita um comando por vez, roda contra a única sessão guardada, transmite de volta.

Os comandos rodam um depois do outro, nunca ao mesmo tempo: `sys.stdout`,
`sys.stdin` e o diretório de trabalho são do processo inteiro, e quem digita
dois comandos na CLI não precisa deles intercalados. Um segundo cliente só
espera na fila do listen.
"""

from __future__ import annotations

import contextlib
import os
import socket
import struct
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from diagnos_cli import context

from . import protocol
from .host import SessionHost
from .streams import InputStream, OutputStream, command_environment

RunCli = Callable[[list[str]], int]


def peer_uid(conn: socket.socket) -> int | None:
    """🇺🇸 The connecting process's uid (Linux `SO_PEERCRED`); `None` where the kernel cannot say.

    🇧🇷 O uid do processo que conectou (`SO_PEERCRED` do Linux); `None` onde o kernel não informa.
    """
    option = getattr(socket, "SO_PEERCRED", None)
    if option is None:
        return None
    _pid, uid, _gid = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, option, struct.calcsize("3i")))
    return int(uid)


class AgentServer:
    """🇺🇸 The accept loop: one command at a time, until `logout`, the idle timeout or a signal.

    🇧🇷 O laço de accept: um comando por vez, até o `logout`, o tempo ocioso ou um sinal.
    """

    def __init__(
        self,
        path: Path,
        *,
        host: SessionHost,
        run_cli: RunCli,
        idle_seconds: float,
        uid_of: Callable[[socket.socket], int | None] = peer_uid,
    ) -> None:
        """🇺🇸 Serves on `path`, running commands with `run_cli`. 🇧🇷 Serve em `path`, rodando comandos com `run_cli`."""
        self._path, self._host, self._run_cli = path, host, run_cli
        self._idle_seconds, self._uid_of = idle_seconds, uid_of

    def serve(self, ready: threading.Event | None = None) -> None:
        """🇺🇸 Binds the socket (`0600`), serves, and always locks the session and removes the socket on the way out.

        🇧🇷 Faz o bind do socket (`0600`), serve, e sempre trava a sessão e remove o socket na saída.
        """
        self._path.unlink(missing_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        context.host_clients(self._host.client_for)
        try:
            listener.bind(str(self._path))
            os.chmod(self._path, 0o600)
            listener.listen(8)
            listener.settimeout(self._idle_seconds)
            if ready is not None:
                ready.set()
            while self._accept_one(listener):
                pass
        finally:
            listener.close()
            self._path.unlink(missing_ok=True)
            context.host_clients(None)
            self._host.shutdown()

    def _accept_one(self, listener: socket.socket) -> bool:
        """🇺🇸 Handles one connection; `False` ends the agent (idle timeout or `logout`).

        🇧🇷 Atende uma conexão; `False` encerra o agente (tempo ocioso ou `logout`).
        """
        try:
            conn, _ = listener.accept()
        except TimeoutError:
            return False
        with conn:
            conn.settimeout(None)
            uid = self._uid_of(conn)
            if uid is not None and uid != os.getuid():
                return True
            try:
                return self._handle(conn)
            except (OSError, protocol.ProtocolViolation):
                return True

    def _handle(self, conn: socket.socket) -> bool:
        """🇺🇸 Dispatches one request frame. 🇧🇷 Despacha um frame de requisição."""
        reader = protocol.Reader(conn)
        request = reader.next()
        if request is None:
            return True
        if request["type"] == "ping":
            protocol.send(conn, {"type": "pong", **self._host.status()})
            return True
        if request["type"] != "run":
            return True
        code = self._run(conn, reader, request)
        stop = context.consume_agent_stop()
        if stop:
            # 🇺🇸 `logout`: revoke and wipe before the reply, so the client returns only once the session is gone.
            # 🇧🇷 `logout`: revoga e apaga antes da resposta, para o cliente só voltar com a sessão já encerrada.
            self._host.shutdown()
        # 🇺🇸 A caller gone by now (Ctrl-C) changes nothing: a `logout` still stops the agent.
        # 🇧🇷 Quem chamou já ter saído (Ctrl-C) não muda nada: um `logout` ainda para o agente.
        with contextlib.suppress(OSError):
            protocol.send(conn, {"type": "exit", "code": code})
        return not stop

    def _run(self, conn: socket.socket, reader: protocol.Reader, request: dict[str, Any]) -> int:
        """🇺🇸 Runs the command with the client's cwd, variables and streams; any crash is exit code 1.

        🇧🇷 Roda o comando com o cwd, as variáveis e os fluxos do cliente; qualquer quebra é código de saída 1.
        """
        lock = threading.Lock()
        streams = (
            OutputStream(conn, lock, "out", bool(request.get("stdout_tty"))),
            OutputStream(conn, lock, "err", bool(request.get("stderr_tty"))),
            InputStream(conn, reader, lock),
        )
        argv = [str(arg) for arg in request.get("argv", [])]
        env = {str(key): str(value) for key, value in dict(request.get("env", {})).items()}
        try:
            with command_environment(str(request.get("cwd", "/")), env, streams):
                return self._run_cli(argv)
        except Exception:  # noqa: BLE001 — one broken command must not take the session down with it
            return 1
        finally:
            self._host.end_command()
