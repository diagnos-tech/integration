"""Clock offset against the vault, the one thing signing depends on.

`X-Signature-Timestamp` must land within ±120 s of the vault's clock
(`docs/PROTOCOL.md §2`). A laptop with an off system clock, or a container
with no NTP, would otherwise sign every request into a `401
SignatureTimestampSkew`. `GET /time` is the one endpoint the vault answers
before any session exists, so the SDK uses it, three times and taking the
median round-trip offset, to correct for that before signing anything.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable

import httpx

ROUND_TRIPS = 3


def _default_now_ms() -> float:
    """Return the wall clock in milliseconds, the same unit the vault's `/time` speaks."""
    return time.time() * 1000


class ClockSync:
    """Track `offset_ms = server_clock − local_clock` for one transport."""

    def __init__(self, now_ms: Callable[[], float] = _default_now_ms) -> None:
        """Create an unsynced clock.

        Args:
            now_ms: The local clock in milliseconds. It defaults to the wall clock and is injectable so that tests
                can drive a fake clock instead of racing the real one.
        """
        self._now_ms = now_ms
        self._offset_ms = 0.0
        self._synced = False

    @property
    def is_synced(self) -> bool:
        """Whether `sync()` has run at least once."""
        return self._synced

    @property
    def offset_ms(self) -> float:
        """The median offset from the last `sync()`; `0.0` before the first one."""
        return self._offset_ms

    def sync(self, client: httpx.Client) -> None:
        """Call `GET /time` three times against `client`'s `base_url` and keep the median offset.

        The median, not the mean, throws out a single round trip that hit a
        slow network hop instead of letting it drag the whole estimate off.
        The response is a raw `{"result": <server_ms>}`, not the envelope,
        because `/time` predates having a session to sign with.

        Args:
            client: An HTTP client whose `base_url` is the vault.

        Raises:
            httpx.HTTPStatusError: If `/time` answers with an error status.
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
        """Return the current time, corrected by the offset, as whole Unix seconds.

        This is the exact value that goes into `X-Signature-Timestamp`.
        """
        return int((self._now_ms() + self._offset_ms) / 1000)
