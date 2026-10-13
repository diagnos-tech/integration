"""🇺🇸 Stand-ins for `sys.stdout`, `sys.stderr` and `sys.stdin` that talk to the caller over the socket.

A command inside the agent writes and reads exactly as it would in the
caller's shell; these objects turn that into frames, and
`command_environment` swaps them in (with the caller's directory and
presentation variables) for one command.

🇧🇷 Substitutos de `sys.stdout`, `sys.stderr` e `sys.stdin` que falam com quem chamou pelo socket.

Um comando dentro do agente escreve e lê exatamente como faria no shell de
quem chamou; estes objetos transformam isso em frames, e
`command_environment` os coloca no lugar (com o diretório e as variáveis de
apresentação de quem chamou) durante um comando.
"""

from __future__ import annotations

import contextlib
import io
import os
import socket
import sys
import threading
from collections.abc import Iterator, Mapping
from typing import Any

from . import protocol
from .protocol import FORWARDED_ENV


class OutputStream:
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


class InputStream:
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
def command_environment(cwd: str, env: Mapping[str, str], streams: tuple[Any, Any, Any]) -> Iterator[None]:
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
