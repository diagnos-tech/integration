"""`configure_logging`: one JSON object per `diagnos.api`/`diagnos` log line, exceptions included."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from diagnos.api.logging import configure_logging


@pytest.fixture(autouse=True)
def _restore_logger_state() -> Iterator[None]:
    """Restores the two process-global loggers that `configure_logging` mutates after every test.

    Without this, a `handlers` or `propagate` change from one test would leak into whichever test (in this file or any
    other) next triggers a `diagnos.api` or `diagnos` log call.
    """
    snapshots = {
        name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level, logging.getLogger(name).propagate)
        for name in ("diagnos.api", "diagnos")
    }
    yield
    for name, (handlers, level, propagate) in snapshots.items():
        logger = logging.getLogger(name)
        logger.handlers = handlers
        logger.level = level
        logger.propagate = propagate


def test_configure_logging_emits_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    """A plain `logger.info` call renders as one parseable JSON line with `timestamp`/`level`/`logger`/`message`."""
    configure_logging()
    logger = logging.getLogger("diagnos.api")

    logger.info("vault session unlocked; serving requests")

    line = capsys.readouterr().out.strip()
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "diagnos.api"
    assert payload["message"] == "vault session unlocked; serving requests"
    assert "exc_info" not in payload


def test_configure_logging_attaches_a_formatted_traceback_on_exception(capsys: pytest.CaptureFixture[str]) -> None:
    """`logger.exception` (as `errors._unexpected_error_handler` calls it) adds an `exc_info` field."""
    configure_logging()
    logger = logging.getLogger("diagnos.api")

    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("unhandled diagnos error")

    payload = json.loads(capsys.readouterr().out.strip())
    assert "exc_info" in payload
    assert "ValueError: boom" in payload["exc_info"]


def test_configure_logging_disables_propagation_to_the_root_logger() -> None:
    """`propagate = False` is what stops a doubled line if the root logger also has a handler."""
    configure_logging()

    assert logging.getLogger("diagnos.api").propagate is False
    assert logging.getLogger("diagnos").propagate is False
    assert len(logging.getLogger("diagnos.api").handlers) == 1
