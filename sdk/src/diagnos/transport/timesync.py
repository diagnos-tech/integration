"""🇺🇸 Clock offset against the vault — the one thing signing depends on.

`X-Signature-Timestamp` must land within ±120 s of the vault's clock (`docs/PROTOCOL.md
§2`); a laptop with an off system clock or a container with no NTP would
otherwise sign every request into a `401 SignatureTimestampSkew`. `GET /time`
is the one endpoint the vault answers before any session exists, so the SDK
uses it — three times, taking the median round-trip offset — to correct for
that before signing anything.

🇧🇷 Diferença de relógio contra o cofre — a única coisa de que a assinatura
depende.

`X-Signature-Timestamp` precisa cair dentro de ±120 s do relógio do cofre
(`docs/PROTOCOL.md §2`); um notebook com relógio errado ou um container sem
NTP assinaria toda requisição rumo a um `401 SignatureTimestampSkew`. `GET
/time` é o único endpoint que o cofre responde antes de qualquer sessão
existir, então o SDK o usa — três vezes, tomando a mediana do offset de ida
e volta — para corrigir isso antes de assinar qualquer coisa.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable

import httpx

ROUND_TRIPS = 3


def _default_now_ms() -> float:
    """🇺🇸 Wall clock in milliseconds, the same unit the vault's `/time` speaks.

    🇧🇷 Relógio de parede em milissegundos, a mesma unidade que `/time` fala.
    """
    return time.time() * 1000


class ClockSync:
    """🇺🇸 Tracks `offset_ms = server_clock − local_clock` for one transport.

    🇧🇷 Acompanha `offset_ms = relógio_do_servidor − relógio_local` para um transporte.
    """

    def __init__(self, now_ms: Callable[[], float] = _default_now_ms) -> None:
        """🇺🇸 `now_ms` defaults to the wall clock; tests inject a fake one.

        🇧🇷 `now_ms` usa o relógio de parede por padrão; testes injetam um falso.
        """
        # 🇺🇸 Injectable so tests can drive a fake clock instead of racing the real one.
        # 🇧🇷 Injetável para os testes controlarem um relógio falso em vez de correr contra o de verdade.
        self._now_ms = now_ms
        self._offset_ms = 0.0
        self._synced = False

    @property
    def is_synced(self) -> bool:
        """🇺🇸 False until `sync()` has run at least once. 🇧🇷 Falso até `sync()` rodar ao menos uma vez."""
        return self._synced

    @property
    def offset_ms(self) -> float:
        """🇺🇸 The median offset from the last `sync()`; `0.0` before the first one.

        🇧🇷 O offset mediano do último `sync()`; `0.0` antes do primeiro.
        """
        return self._offset_ms

    def sync(self, client: httpx.Client) -> None:
        """🇺🇸 `GET /time` three times against `client`'s `base_url` and take the median offset.

        The median, not the mean, throws out a single round-trip that hit a
        slow network hop instead of letting it drag the whole estimate off.
        The response is a raw `{"result": <server_ms>}`, not the envelope —
        `/time` predates having a session to sign with.

        🇧🇷 `GET /time` três vezes contra o `base_url` do `client` e usa a mediana do offset.

        A mediana, não a média, descarta uma ida e volta que pegou um salto de
        rede lento em vez de deixar isso puxar a estimativa toda. A resposta é
        um `{"result": <ms_do_servidor>}` cru, não o envelope — `/time` é
        anterior a existir sessão para assinar.
        """
        offsets: list[float] = []
        for _ in range(ROUND_TRIPS):
            t0 = self._now_ms()
            response = client.get("/time")
            t1 = self._now_ms()
            response.raise_for_status()
            server_ms = float(response.json()["result"])
            offsets.append(server_ms - (t0 + t1) / 2)
        self._offset_ms = statistics.median(offsets)
        self._synced = True

    def now_seconds(self) -> int:
        """🇺🇸 Current time, corrected by the offset, as whole Unix seconds.

        The exact text that goes into `X-Signature-Timestamp`.

        🇧🇷 Hora atual, corrigida pelo offset, em segundos Unix inteiros.

        O texto exato que vai em `X-Signature-Timestamp`.
        """
        return int((self._now_ms() + self._offset_ms) / 1000)
