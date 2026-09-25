"""🇺🇸 `ClockSync`: three `/time` round trips collapse into one median offset.

The median matters concretely: a single slow round trip (a GC pause, a
scheduler hiccup) must not drag the offset toward it the way a mean would,
because every signature after `sync()` depends on that offset being close to
the vault's real clock.

🇧🇷 `ClockSync`: três idas e volta a `/time` viram um único offset mediano.

A mediana importa na prática: uma única ida e volta lenta (pausa de GC,
soluço do agendador) não pode puxar o offset na direção dela do jeito que
uma média puxaria, porque toda assinatura depois de `sync()` depende desse
offset estar perto do relógio de verdade do cofre.
"""

from __future__ import annotations

import httpx
from diagnos.transport.timesync import ClockSync

# 🇺🇸 A fixed local clock (t0 == t1 on every round trip) turns "offset =
# server_ms - (t0+t1)/2" into "offset = server_ms - BASE_MS", which is enough
# to isolate the median-selection behaviour without simulating elapsed time.
# 🇧🇷 Um relógio local fixo (t0 == t1 em toda ida e volta) transforma "offset =
# server_ms - (t0+t1)/2" em "offset = server_ms - BASE_MS", suficiente para
# isolar o comportamento de seleção da mediana sem simular tempo decorrido.
BASE_MS = 1_700_000_000_000.0


def _client_with_results(results: dict[int, float]) -> httpx.Client:
    """🇺🇸 A client answering the n-th `GET /time` with `results[n]` (1-based).

    🇧🇷 Um client que responde o n-ésimo `GET /time` com `results[n]` (a partir de 1).
    """
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert (request.method, request.url.path) == ("GET", "/time")
        calls["n"] += 1
        return httpx.Response(200, json={"result": results[calls["n"]]})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://vault.example.test")


def test_sync_takes_the_median_offset_ignoring_an_outlier() -> None:
    """🇺🇸 `sync()` settles on the median of three offsets, not the mean.

    🇧🇷 `sync()` fixa a mediana de três offsets, não a média.
    """
    # 🇺🇸 Round 2 is a wild outlier (+900_000 ms); the mean would land near
    # 383_333, nowhere close to either real value.
    # 🇧🇷 A rodada 2 é um outlier absurdo (+900_000 ms); a média cairia perto
    # de 383_333, longe dos dois valores reais.
    results = {1: BASE_MS + 100_000, 2: BASE_MS + 900_000, 3: BASE_MS + 150_000}
    clock = ClockSync(now_ms=lambda: BASE_MS)

    assert clock.is_synced is False

    clock.sync(_client_with_results(results))

    assert clock.is_synced is True
    assert clock.offset_ms == 150_000


def test_now_seconds_applies_the_synced_offset() -> None:
    """🇺🇸 After `sync()`, `now_seconds()` adds the median offset to the local clock.

    🇧🇷 Depois de `sync()`, `now_seconds()` soma o offset mediano ao relógio local.
    """
    results = {1: BASE_MS + 100_000, 2: BASE_MS + 900_000, 3: BASE_MS + 150_000}
    clock = ClockSync(now_ms=lambda: BASE_MS)
    clock.sync(_client_with_results(results))

    assert clock.now_seconds() == int((BASE_MS + 150_000) / 1000)


def test_now_seconds_before_sync_assumes_zero_offset() -> None:
    """🇺🇸 Before the first `sync()`, `now_seconds()` trusts the local clock as-is.

    🇧🇷 Antes do primeiro `sync()`, `now_seconds()` confia no relógio local puro.
    """
    clock = ClockSync(now_ms=lambda: BASE_MS)
    assert clock.now_seconds() == int(BASE_MS / 1000)


def test_sync_makes_exactly_three_round_trips() -> None:
    """🇺🇸 `sync()` calls `/time` exactly three times, per `docs/PROTOCOL.md §2`.

    🇧🇷 `sync()` chama `/time` exatamente três vezes, conforme `docs/PROTOCOL.md §2`.
    """
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"result": BASE_MS})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://vault.example.test")
    ClockSync(now_ms=lambda: BASE_MS).sync(client)

    assert calls["n"] == 3
