"""🇺🇸 The wire between a `diagnos` command and its agent: one JSON object per line, both ways.

Client → agent: `{"type": "run", "argv", "cwd", "env", "stdout_tty", "stderr_tty"}` or `{"type": "ping"}`;
later `{"type": "input", "line"}` answers a prompt. (Stopping is a command like any other: `logout`.)
Agent → client: `{"type": "out" | "err", "data"}` as the command writes, `{"type": "prompt"}` when it
reads a line, and `{"type": "exit", "code"}` last (or `{"type": "pong", …}` for a ping).

🇧🇷 O fio entre um comando `diagnos` e o agente dele: um objeto JSON por linha, nos dois sentidos.

Cliente → agente: `{"type": "run", "argv", "cwd", "env", "stdout_tty", "stderr_tty"}` ou `{"type": "ping"}`;
depois `{"type": "input", "line"}` responde a um prompt. (Parar é um comando como outro qualquer: `logout`.)
Agente → cliente: `{"type": "out" | "err", "data"}` conforme o comando escreve, `{"type": "prompt"}` quando ele
lê uma linha, e `{"type": "exit", "code"}` por último (ou `{"type": "pong", …}` para um ping).
"""

from __future__ import annotations

import json
import socket
from typing import Any, Final

# 🇺🇸 A frame is a command line or a chunk of output — far below this; a peer sending more is broken or hostile.
# 🇧🇷 Um frame é uma linha de comando ou um pedaço de saída — muito abaixo disto; um par que manda mais está
#    quebrado ou é hostil.
MAX_FRAME_BYTES: Final = 4 * 1024 * 1024

# 🇺🇸 The only variables a client may set for its command: presentation, and the group default. The agent's
#    identity and configuration are the ones it started with.
# 🇧🇷 As únicas variáveis que um cliente pode definir para o comando dele: apresentação, e o grupo padrão. A
#    identidade e a configuração do agente são as com que ele subiu.
FORWARDED_ENV: Final = ("DIAGNOS_GROUP", "NO_COLOR", "FORCE_COLOR", "COLUMNS", "LINES", "TERM", "COLORTERM")


class ProtocolViolation(Exception):  # noqa: N818 — named after the condition, like `ConnectionResetError`
    """🇺🇸 The other side sent something that is not a frame. 🇧🇷 O outro lado mandou algo que não é um frame."""


def send(conn: socket.socket, message: dict[str, Any]) -> None:
    """🇺🇸 Writes one frame. 🇧🇷 Escreve um frame."""
    conn.sendall(json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")


class Reader:
    """🇺🇸 Reads frames off a socket, one line at a time. 🇧🇷 Lê frames de um socket, uma linha por vez."""

    def __init__(self, conn: socket.socket) -> None:
        """🇺🇸 Wraps `conn`. 🇧🇷 Embrulha `conn`."""
        self._conn = conn
        self._buffer = bytearray()

    def next(self) -> dict[str, Any] | None:
        """🇺🇸 The next frame, or `None` when the other side closed the connection.

        🇧🇷 O próximo frame, ou `None` quando o outro lado fechou a conexão.
        """
        while b"\n" not in self._buffer:
            if len(self._buffer) > MAX_FRAME_BYTES:
                raise ProtocolViolation("frame too large")
            try:
                chunk = self._conn.recv(65536)
            except ConnectionResetError:
                # 🇺🇸 The peer closed with our frame unread (it refused us, or died): gone all the same.
                # 🇧🇷 O par fechou com nosso frame sem ler (nos recusou, ou morreu): foi embora do mesmo jeito.
                return None
            if not chunk:
                return None
            self._buffer.extend(chunk)
        line, _, rest = bytes(self._buffer).partition(b"\n")
        self._buffer = bytearray(rest)
        try:
            message = json.loads(line)
        except ValueError as exc:
            raise ProtocolViolation("frame is not JSON") from exc
        if not isinstance(message, dict) or not isinstance(message.get("type"), str):
            raise ProtocolViolation("frame has no type")
        return message
