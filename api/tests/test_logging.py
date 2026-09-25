"""🇺🇸 `configure_logging`: one JSON object per `diagnos_api`/`diagnos` log line, exceptions included.

🇧🇷 `configure_logging`: um objeto JSON por linha de log de `diagnos_api`/`diagnos`, exceções inclusas.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from diagnos_api.logging import configure_logging


@pytest.fixture(autouse=True)
def _restore_logger_state() -> Iterator[None]:
    """🇺🇸 `configure_logging` mutates two process-global loggers — every test gets them back afterwards.

    Without this, a `handlers`/`propagate` change from one test would leak
    into whichever test (in this file or any other) next triggers a
    `diagnos_api`/`diagnos` log call.

    🇧🇷 `configure_logging` muda dois loggers globais do processo — todo
    teste os recebe de volta depois.

    Sem isto, uma mudança de `handlers`/`propagate` de um teste vazaria para
    o próximo teste (deste arquivo ou de qualquer outro) que disparar uma
    chamada de log de `diagnos_api`/`diagnos`.
    """
    snapshots = {
        name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level, logging.getLogger(name).propagate)
        for name in ("diagnos_api", "diagnos")
    }
    yield
    for name, (handlers, level, propagate) in snapshots.items():
        logger = logging.getLogger(name)
        logger.handlers = handlers
        logger.level = level
        logger.propagate = propagate


def test_configure_logging_emits_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 A plain `logger.info` call renders as one parseable JSON line with `timestamp`/`level`/`logger`/`message`.

    🇧🇷 Uma chamada simples de `logger.info` renderiza como uma linha JSON parseável com
    `timestamp`/`level`/`logger`/`message`.
    """
    configure_logging()
    logger = logging.getLogger("diagnos_api")

    logger.info("vault session unlocked; serving requests")

    line = capsys.readouterr().out.strip()
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "diagnos_api"
    assert payload["message"] == "vault session unlocked; serving requests"
    assert "exc_info" not in payload


def test_configure_logging_attaches_a_formatted_traceback_on_exception(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `logger.exception` (as `errors._unexpected_error_handler` calls it) adds an `exc_info` field.

    🇧🇷 `logger.exception` (como `errors._unexpected_error_handler` chama) acrescenta um campo `exc_info`.
    """
    configure_logging()
    logger = logging.getLogger("diagnos_api")

    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("unhandled diagnos error")

    payload = json.loads(capsys.readouterr().out.strip())
    assert "exc_info" in payload
    assert "ValueError: boom" in payload["exc_info"]


def test_configure_logging_disables_propagation_to_the_root_logger() -> None:
    """🇺🇸 `propagate = False` is what stops a doubled line if the root logger also has a handler.

    🇧🇷 `propagate = False` é o que impede uma linha duplicada se o logger raiz também tiver um handler.
    """
    configure_logging()

    assert logging.getLogger("diagnos_api").propagate is False
    assert logging.getLogger("diagnos").propagate is False
    assert len(logging.getLogger("diagnos_api").handlers) == 1
