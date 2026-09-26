"""🇺🇸 `python -m diagnos_cli.agent --socket PATH --idle SECONDS` — what `diagnos login` starts, detached.

🇧🇷 `python -m diagnos_cli.agent --socket PATH --idle SECONDS` — o que o `diagnos login` sobe, destacado.
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path
from types import FrameType

from .server import AgentServer, SessionHost


def _exit(signum: int, frame: FrameType | None) -> None:
    """🇺🇸 `SIGTERM` unwinds through `serve()`'s `finally`: lock, wipe, remove the socket.

    🇧🇷 O `SIGTERM` desenrola pelo `finally` do `serve()`: trava, apaga, remove o socket.
    """
    sys.exit(0)


def main(argv: list[str] | None = None) -> None:
    """🇺🇸 Serves until `logout`, the idle timeout or `SIGTERM`. 🇧🇷 Serve até o `logout`, o ócio ou um `SIGTERM`."""
    parser = argparse.ArgumentParser(prog="python -m diagnos_cli.agent")
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--idle", required=True, type=float)
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, _exit)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    from diagnos_cli.main import run  # noqa: PLC0415 — the CLI imports this package; import at use to avoid a cycle

    AgentServer(args.socket, host=SessionHost(), run_cli=run, idle_seconds=args.idle).serve()


if __name__ == "__main__":
    main()
