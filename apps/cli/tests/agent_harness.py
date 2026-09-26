"""🇺🇸 Runs the real session agent in a thread, over a real Unix socket, with a fake SDK behind it.

Everything but the SDK is production code: `AgentServer`, `SessionHost`, the
wire protocol, `client.relay` and `main.run`. Sockets go under a short
`mkdtemp` directory because a Unix socket path is limited to ~104 bytes and
pytest's `tmp_path` can be longer.

🇧🇷 Roda o agente de sessão de verdade numa thread, por um socket Unix de verdade, com um SDK falso por trás.

Tudo menos o SDK é código de produção: `AgentServer`, `SessionHost`, o
protocolo do fio, `client.relay` e `main.run`. Os sockets ficam num
diretório curto de `mkdtemp` porque o caminho de um socket Unix é limitado
a ~104 bytes e o `tmp_path` do pytest pode ser mais longo.
"""

from __future__ import annotations

import io
import os
import shutil
import socket
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from diagnos_cli.agent import client
from diagnos_cli.agent.server import AgentServer, SessionHost
from diagnos_cli.main import run


@dataclass
class RunningAgent:
    """🇺🇸 A live agent and a way to run commands through it. 🇧🇷 Um agente vivo e um jeito de rodar comandos por ele."""

    path: Path
    host: SessionHost
    thread: threading.Thread
    clients_made: list[Any] = field(default_factory=list)

    def run(self, argv: list[str], *, stdin: str = "", env: dict[str, str] | None = None) -> tuple[int, str, str]:
        """🇺🇸 `(exit code, stdout, stderr)` of `argv` run by the agent. 🇧🇷 `(código, stdout, stderr)` de `argv`."""
        out, err = io.StringIO(), io.StringIO()
        conn = client.connect(self.path)
        assert conn is not None, "agent is not listening · o agente não está escutando"
        with conn:
            code = client.relay(conn, argv, env=env or {}, stdin=io.StringIO(stdin), stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def stopped(self, timeout: float = 5.0) -> bool:
        """🇺🇸 Waits for the agent to exit. 🇧🇷 Espera o agente sair."""
        self.thread.join(timeout)
        return not self.thread.is_alive()


@contextmanager
def socket_directory(path: Path | None = None) -> Iterator[Path]:
    """🇺🇸 A short, private (`0700`) directory for sockets, removed afterwards.

    🇧🇷 Um diretório curto e privado (`0700`) para sockets, removido depois.
    """
    directory = Path(tempfile.mkdtemp(prefix="dg"))
    os.chmod(directory, 0o700)
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@contextmanager
def running_agent(
    vault: Any,
    *,
    path: Path | None = None,
    idle_seconds: float = 10.0,
    run_cli: Callable[[list[str]], int] = run,
    uid_of: Callable[[socket.socket], int | None] | None = None,
) -> Iterator[RunningAgent]:
    """🇺🇸 Serves `vault` (any fake with the `Diagnos` surface) until the block ends or the agent stops itself.

    🇧🇷 Serve `vault` (qualquer fake com a superfície de `Diagnos`) até o bloco acabar ou o agente parar sozinho.
    """
    with socket_directory() as directory:
        socket_path = path or directory / "agent.sock"
        made: list[Any] = []

        def make_client(options: Any, *, on_prompt: Any = None, auto_unseal: Any = None) -> Any:
            """🇺🇸 Hands out `vault`, recording each construction. 🇧🇷 Entrega `vault`, registrando cada construção."""
            made.append(on_prompt)
            bind = getattr(vault, "bind_prompt", None)
            if bind is not None:
                bind(on_prompt)
            return vault

        host = SessionHost(make_client=make_client)
        extra = {"uid_of": uid_of} if uid_of is not None else {}
        server = AgentServer(socket_path, host=host, run_cli=run_cli, idle_seconds=idle_seconds, **extra)
        ready = threading.Event()
        thread = threading.Thread(target=server.serve, args=(ready,), daemon=True)
        thread.start()
        assert ready.wait(5), "agent did not start · o agente não subiu"
        agent = RunningAgent(socket_path, host, thread, made)
        try:
            yield agent
        finally:
            # 🇺🇸 A test that already stopped the agent may still be unwinding it: only a listening agent is told.
            # 🇧🇷 Um teste que já parou o agente pode ainda estar desmontando-o: só um agente escutando é avisado.
            conn = client.connect(socket_path)
            if conn is not None:
                with conn:
                    client.relay(
                        conn, ["logout"], env={}, stdin=io.StringIO(), stdout=io.StringIO(), stderr=io.StringIO()
                    )
            assert agent.stopped(), "agent did not stop · o agente não parou"
