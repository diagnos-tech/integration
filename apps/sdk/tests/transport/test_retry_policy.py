"""🇺🇸 `transport/_retry.py`: `Retry-After` parsing and the jittered `429` backoff, unit and end-to-end.

`retry_after_seconds`/`rate_limit_wait_seconds` are pure functions over an
`httpx.Response` and an attempt count, so the first half of this file calls
them directly — no transport, no signing. The second half drives a real
`VaultTransport` over `httpx.MockTransport`, the same way `test_http.py`
does, specifically for the one path `test_http.py` never exercises: a `429`
with **no** `Retry-After` header, which is the only way `rate_limit_wait_seconds`
ever reaches its own jittered-backoff branch instead of trusting the header.

🇧🇷 `transport/_retry.py`: parse de `Retry-After` e o backoff com jitter de
`429`, em unidade e ponta a ponta.

`retry_after_seconds`/`rate_limit_wait_seconds` são funções puras sobre uma
`httpx.Response` e uma contagem de tentativas, então a primeira metade deste
arquivo as chama direto — sem transporte, sem assinatura. A segunda metade
roda um `VaultTransport` de verdade sobre `httpx.MockTransport`, do mesmo
jeito que `test_http.py` faz, especificamente para o único caminho que
`test_http.py` nunca exercita: um `429` **sem** header `Retry-After`, o único
jeito de `rate_limit_wait_seconds` chegar ao próprio ramo de backoff com
jitter em vez de confiar no header.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from diagnos.errors import RateLimitError
from diagnos.transport._retry import (
    MAX_RATE_LIMIT_RETRIES,
    RATE_LIMIT_BACKOFFS_SECONDS,
    rate_limit_wait_seconds,
    retry_after_seconds,
)
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.token import ServiceAccountToken

# -- retry_after_seconds / rate_limit_wait_seconds: pure unit tests -----------


def test_retry_after_seconds_is_none_without_the_header() -> None:
    """🇺🇸 No `Retry-After` header at all means "no opinion", not `0`.

    🇧🇷 Nenhum header `Retry-After` significa "sem opinião", não `0`.
    """
    response = httpx.Response(429)
    assert retry_after_seconds(response) is None


def test_retry_after_seconds_parses_a_numeric_header() -> None:
    """🇺🇸 A numeric `Retry-After` (seconds, per PROTOCOL §12) parses to a `float`.

    🇧🇷 Um `Retry-After` numérico (segundos, conforme PROTOCOL §12) vira `float`.
    """
    response = httpx.Response(429, headers={"Retry-After": "3.5"})
    assert retry_after_seconds(response) == 3.5


def test_retry_after_seconds_ignores_a_non_numeric_header() -> None:
    """🇺🇸 A header that is not a number (an HTTP-date, garbage) is treated as absent, not a crash.

    🇧🇷 Um header que não é número (uma data HTTP, lixo) é tratado como ausente, não uma quebra.
    """
    response = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"})
    assert retry_after_seconds(response) is None


def test_rate_limit_wait_seconds_honours_retry_after_over_the_backoff_table() -> None:
    """🇺🇸 A `Retry-After` header wins outright, regardless of the attempt count.

    🇧🇷 Um header `Retry-After` vence direto, não importa a contagem de tentativas.
    """
    response = httpx.Response(429, headers={"Retry-After": "7"})
    assert rate_limit_wait_seconds(response, attempts=0) == 7.0
    assert rate_limit_wait_seconds(response, attempts=2) == 7.0


@pytest.mark.parametrize("attempts", [0, 1, 2, 5])
def test_rate_limit_wait_seconds_without_retry_after_uses_a_jittered_backoff(attempts: int) -> None:
    """🇺🇸 With no `Retry-After`, the wait is the table's backoff plus up to half of it in jitter.

    `attempts` beyond the table's length clamps to its last entry — a caller
    that somehow retried more than `MAX_RATE_LIMIT_RETRIES` still gets a
    sane wait, not an `IndexError`.

    🇧🇷 Sem `Retry-After`, a espera é o backoff da tabela mais até metade dele em jitter.

    `attempts` além do tamanho da tabela trava na última entrada — quem
    chamou e de algum jeito retentou mais que `MAX_RATE_LIMIT_RETRIES` ainda
    recebe uma espera sensata, não um `IndexError`.
    """
    response = httpx.Response(429)
    expected_backoff = RATE_LIMIT_BACKOFFS_SECONDS[min(attempts, len(RATE_LIMIT_BACKOFFS_SECONDS) - 1)]

    wait_seconds = rate_limit_wait_seconds(response, attempts=attempts)

    assert expected_backoff <= wait_seconds <= expected_backoff * 1.5


# -- end-to-end: a 429 storm with no Retry-After header ------------------------

_TOKEN = ServiceAccountToken(
    raw="apikey-test",
    key_id="key_1",
    account_id="acc_1",
    workspace_id="ws_1",
    name="svc@ws_1.diagnos.health",
)
_WIDGET_PATH = "/api/external/v1/workspaces/ws_1/widgets"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """🇺🇸 An `httpx.Client` wired to a `MockTransport` instead of a socket.

    🇧🇷 Um `httpx.Client` ligado a um `MockTransport` em vez de um socket.
    """
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://vault.example.test")


def _envelope_error(code: str, *, status: int) -> httpx.Response:
    """🇺🇸 A `success: false` envelope with no `Retry-After` header at all.

    🇧🇷 Um envelope `success: false` sem header `Retry-After` nenhum.
    """
    return httpx.Response(
        status,
        json={"success": False, "status": "fail", "status_code": status, "errors": [{"code": code}], "docs": "d"},
    )


def test_a_429_storm_with_no_retry_after_still_retries_and_then_raises() -> None:
    """🇺🇸 Without `Retry-After`, `VaultTransport` still retries up to the cap, sleeping a positive, jittered wait.

    This is the one scenario that forces `rate_limit_wait_seconds` into its
    own backoff-table branch (`_retry.py` lines the header-only tests in
    `transport/test_http.py` never reach) — every recorded sleep must come
    from `RATE_LIMIT_BACKOFFS_SECONDS`, never `0`.

    🇧🇷 Sem `Retry-After`, `VaultTransport` ainda retenta até o teto, dormindo
    uma espera positiva e com jitter.

    Este é o único cenário que força `rate_limit_wait_seconds` ao próprio
    ramo da tabela de backoff (linhas de `_retry.py` que os testes só-com-header
    de `transport/test_http.py` nunca alcançam) — todo sono registrado precisa
    vir de `RATE_LIMIT_BACKOFFS_SECONDS`, nunca `0`.
    """
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return httpx.Response(200, json={"result": 1_700_000_000_000})
        attempts["n"] += 1
        return _envelope_error("RateLimitExceeded", status=429)

    settings = Settings(api_token="apikey-test", vault_url="https://vault.example.test")  # noqa: S106
    sleeps: list[float] = []
    transport = VaultTransport(
        settings,
        _TOKEN,
        session_keys=lambda: None,
        client=_client(handler),
        storage_client=_client(lambda r: httpx.Response(200)),
        sleep=sleeps.append,
    )

    with pytest.raises(RateLimitError):
        transport.get(_WIDGET_PATH, signed=False)

    assert attempts["n"] == MAX_RATE_LIMIT_RETRIES + 1  # 🇺🇸/🇧🇷 initial + every retry · inicial + toda retentativa
    assert len(sleeps) == MAX_RATE_LIMIT_RETRIES
    for wait_seconds, backoff in zip(sleeps, RATE_LIMIT_BACKOFFS_SECONDS, strict=True):
        assert backoff <= wait_seconds <= backoff * 1.5
