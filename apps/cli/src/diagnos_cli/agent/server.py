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
import io
import os
import socket
import struct
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, Final

from diagnos import Diagnos, EnrollmentPrompt

from diagnos_cli import context
from diagnos_cli.context import CliOptions

from . import protocol

# 🇺🇸 The only variables a client may set for its command: presentation, and the group default. The agent's
#    identity and configuration are the ones it started with.
# 🇧🇷 As únicas variáveis que um cliente pode definir para o comando dele: apresentação, e o grupo padrão. A
#    identidade e a configuração do agente são as com que ele subiu.
FORWARDED_ENV: Final = ("DIAGNOS_GROUP", "NO_COLOR", "FORCE_COLOR", "COLUMNS", "LINES", "TERM", "COLORTERM")

RunCli = Callable[[list[str]], int]


class SessionHost:
    """🇺🇸 Owns the agent's one `Diagnos` and routes its enrollment prompt to whichever command is running.

    🇧🇷 Dono da única `Diagnos` do agente, e roteia o prompt de enrollment para o comando que estiver rodando.
    """

    def __init__(self, make_client: Callable[..., Diagnos] = context.make_client) -> None:
        """🇺🇸 `make_client` builds the real client on the first command. 🇧🇷 `make_client` constrói o client real."""
        self._make_client = make_client
        self._vault: Diagnos | None = None
        self._prompt: Callable[[EnrollmentPrompt], None] | None = None
        self.started_at = time.time()

    def client_for(
        self,
        options: CliOptions,
        on_prompt: Callable[[EnrollmentPrompt], None] | None,
        auto_unseal: bool | None,
    ) -> Diagnos:
        """🇺🇸 `context.build_client` inside the agent: always the same client, whatever the command.

        🇧🇷 O `context.build_client` dentro do agente: sempre o mesmo client, seja qual for o comando.
        """
        self._prompt = on_prompt
        if self._vault is None:
            self._vault = self._make_client(options, on_prompt=self._relay_prompt, auto_unseal=auto_unseal)
        return self._vault

    def _relay_prompt(self, prompt: EnrollmentPrompt) -> None:
        """🇺🇸 A (re-)enrollment shows its link on the terminal of the command that triggered it.

        🇧🇷 Um (re)enrollment mostra o link no terminal do comando que o disparou.
        """
        if self._prompt is not None:
            self._prompt(prompt)

    def end_command(self) -> None:
        """🇺🇸 Forgets the finished command's prompt callback. 🇧🇷 Esquece o callback de prompt do comando que acabou."""
        self._prompt = None

    def status(self) -> dict[str, Any]:
        """🇺🇸 What `diagnos status` shows about this agent. 🇧🇷 O que o `diagnos status` mostra sobre este agente."""
        groups = self._vault.security_groups if self._vault is not None else []
        return {"pid": os.getpid(), "started_at": int(self.started_at), "unlocked": bool(groups), "groups": groups}

    def shutdown(self) -> None:
        """🇺🇸 Revokes the session and wipes its keys — an agent never leaves a live session behind.

        🇧🇷 Revoga a sessão e apaga as chaves — um agente nunca deixa uma sessão viva para trás.
        """
        if self._vault is None:
            return
        try:
            # 🇺🇸 Best effort on the way out: an unreachable vault must not keep the keys alive in memory.
            # 🇧🇷 Melhor esforço na saída: um cofre inalcançável não pode manter as chaves vivas na memória.
            with contextlib.suppress(Exception):
                self._vault.lock()
        finally:
            self._vault.close()
            self._vault = None


class _Stream:
    """🇺🇸 A `sys.stdout`/`sys.stderr` that forwards every write to the client as a frame.

    Deliberately not an `io` subclass: it has no file descriptor, and `print`,
    `click` and `rich` only need `write`, `flush` and `isatty`.

    🇧🇷 Um `sys.stdout`/`sys.stderr` que repassa toda escrita ao cliente como um frame.

    De propósito não é subclasse de `io`: não tem descritor de arquivo, e
    `print`, `click` e `rich` só precisam de `write`, `flush` e `isatty`.
    """

    encoding = "utf-8"
    errors = "strict"

    def __init__(self, conn: socket.socket, lock: threading.Lock, kind: str, tty: bool) -> None:
        """🇺🇸 `tty` mirrors the client's terminal, so colors and spinners match what it would see locally.

        🇧🇷 `tty` espelha o terminal do cliente, para cores e spinners baterem com o que ele veria localmente.
        """
        self._conn, self._lock, self._kind, self._tty = conn, lock, kind, tty

    def write(self, data: str) -> int:
        """🇺🇸 Sends `data` now — a spinner's refresh thread writes too, hence the lock.

        🇧🇷 Manda `data` agora — a thread de refresh de um spinner também escreve, daí o lock.
        """
        if not isinstance(data, str):
            # 🇺🇸 Like any text stream. `click` probes with `write(b"")` and would otherwise treat this as binary.
            # 🇧🇷 Como todo fluxo de texto. O `click` testa com `write(b"")` e senão trataria isto como binário.
            raise TypeError(f"write() argument must be str, not {type(data).__name__}")
        if data:
            with self._lock:
                protocol.send(self._conn, {"type": self._kind, "data": data})
        return len(data)

    def isatty(self) -> bool:
        """🇺🇸 Whether the client's stream is a terminal. 🇧🇷 Se o fluxo do cliente é um terminal."""
        return self._tty

    def flush(self) -> None:
        """🇺🇸 Every write is already sent. 🇧🇷 Toda escrita já foi mandada."""

    def fileno(self) -> int:
        """🇺🇸 No descriptor: callers fall back to plain `write`. 🇧🇷 Sem descritor: quem chama cai no `write`."""
        raise io.UnsupportedOperation("fileno")


class _Input:
    """🇺🇸 A `sys.stdin` that asks the client for each line (a confirmation prompt, say).

    🇧🇷 Um `sys.stdin` que pede cada linha ao cliente (um prompt de confirmação, por exemplo).
    """

    def __init__(self, conn: socket.socket, reader: protocol.Reader, lock: threading.Lock) -> None:
        """🇺🇸 Reads replies from `reader`. 🇧🇷 Lê as respostas de `reader`."""
        self._conn, self._reader, self._lock = conn, reader, lock

    def readline(self, size: int = -1) -> str:
        """🇺🇸 One line from the client's stdin; `""` (end of input) if it has none or went away.

        🇧🇷 Uma linha do stdin do cliente; `""` (fim da entrada) se ele não tiver ou tiver sumido.
        """
        try:
            with self._lock:
                protocol.send(self._conn, {"type": "prompt"})
        except OSError:
            return ""
        reply = self._reader.next()
        if reply is None or reply.get("type") != "input":
            return ""
        return str(reply.get("line", ""))

    def isatty(self) -> bool:
        """🇺🇸 Never a terminal on this side. 🇧🇷 Nunca um terminal deste lado."""
        return False

    def fileno(self) -> int:
        """🇺🇸 No descriptor: `input()` then reads through `readline`. 🇧🇷 Sem descritor: `input()` lê por `readline`."""
        raise io.UnsupportedOperation("fileno")


@contextlib.contextmanager
def _command_environment(cwd: str, env: Mapping[str, str], streams: tuple[Any, Any, Any]) -> Iterator[None]:
    """🇺🇸 The client's directory, presentation variables and streams, for one command — then all restored.

    🇧🇷 O diretório, as variáveis de apresentação e os fluxos do cliente, para um comando — depois tudo restaurado.
    """
    saved_streams = (sys.stdout, sys.stderr, sys.stdin)
    saved_cwd = os.getcwd()
    saved_env = {key: os.environ.get(key) for key in FORWARDED_ENV}
    try:
        os.chdir(cwd)
        for key in FORWARDED_ENV:
            os.environ.pop(key, None)
        os.environ.update({key: value for key, value in env.items() if key in FORWARDED_ENV})
        sys.stdout, sys.stderr, sys.stdin = streams
        yield
    finally:
        sys.stdout, sys.stderr, sys.stdin = saved_streams
        os.chdir(saved_cwd)
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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
            _Stream(conn, lock, "out", bool(request.get("stdout_tty"))),
            _Stream(conn, lock, "err", bool(request.get("stderr_tty"))),
            _Input(conn, reader, lock),
        )
        argv = [str(arg) for arg in request.get("argv", [])]
        env = {str(key): str(value) for key, value in dict(request.get("env", {})).items()}
        try:
            with _command_environment(str(request.get("cwd", "/")), env, streams):
                return self._run_cli(argv)
        except Exception:  # noqa: BLE001 — one broken command must not take the session down with it
            return 1
        finally:
            self._host.end_command()
