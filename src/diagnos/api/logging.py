"""Structured logging: one JSON object per line, for the `diagnos.api` and `diagnos` loggers.

A container platform (`apps/api/deploy/k8s`) ships stdout to a log aggregator line by line; JSON per line lets that
aggregator index level, logger name and message without a fragile regex over free text. What never appears in a field
here matters as much as the format: a request body can carry a patient's legal name, a token carries a bearer
credential, and a filename can itself be sensitive (`chest_ct_re_biopsy.dcm`). None of that belongs in a log, so no code
in this package passes one of those to `logger.info` or `logger.error` (`CONVENTIONS.md`'s "secrets never logged",
extended here to clinical content in general).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_STRUCTURED_LOGGERS = ("diagnos.api", "diagnos")


class _JsonLineFormatter(logging.Formatter):
    """Renders one `logging.LogRecord` as one line of JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Returns the `timestamp`, `level`, `logger` and `message` fields, plus `exc_info` for an exception."""
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Points `diagnos.api` and `diagnos` at one JSON-line `stdout` handler each; idempotent.

    Called once from `main.run()`, before `uvicorn.run(..., log_config=None)`. Passing `log_config=None` is what stops
    uvicorn from installing its own logging configuration on top of this one.

    Args:
        level: The level set on both loggers.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonLineFormatter())
    for name in _STRUCTURED_LOGGERS:
        target = logging.getLogger(name)
        target.handlers = [handler]
        target.setLevel(level)
        target.propagate = False
