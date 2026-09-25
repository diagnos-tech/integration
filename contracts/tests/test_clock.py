"""🇺🇸 `GET /time` — the one call the SDK makes before it can sign anything (`docs/PROTOCOL.md §2`).

🇧🇷 `GET /time` — a única chamada que o SDK faz antes de conseguir assinar qualquer coisa (`docs/PROTOCOL.md §2`).
"""

from __future__ import annotations

import httpx
from diagnos.transport.timesync import ClockSync
from pact import Pact

from _wire import SERVER_TIME_MS, declare_clock


def test_clock_sync_reads_the_vaults_time(pact: Pact) -> None:
    """🇺🇸 The raw `{"result"}` answer (not the envelope) is what the offset is computed from.

    🇧🇷 A resposta crua `{"result"}` (não o envelope) é de onde o offset é calculado.
    """
    declare_clock(pact)
    local_ms = SERVER_TIME_MS - 90_000
    clock = ClockSync(now_ms=lambda: local_ms)
    with pact.serve() as server, httpx.Client(base_url=str(server.url)) as client:
        clock.sync(client)

    assert clock.offset_ms == 90_000
