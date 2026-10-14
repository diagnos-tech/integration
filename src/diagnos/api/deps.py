"""The one FastAPI dependency every router needs: the live `Diagnos` this process holds."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from diagnos import Diagnos


def get_vault(request: Request) -> Diagnos:
    """Returns the single `Diagnos` that `create_app` built or was given, shared by every request.

    Reading it from `request.app.state` (set once, in `create_app`) instead of a module-level global lets
    `conftest.py` swap in a fake `Diagnos` per test without leaking process-wide state between tests.
    """
    return cast(Diagnos, request.app.state.vault)
