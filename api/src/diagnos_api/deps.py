"""🇺🇸 The one shared FastAPI dependency every router needs: the live `Diagnos` this process holds.

🇧🇷 A única dependência do FastAPI que toda rota precisa: o `Diagnos` vivo que este processo guarda.
"""

from __future__ import annotations

from typing import cast

from diagnos import Diagnos
from fastapi import Request


def get_vault(request: Request) -> Diagnos:
    """🇺🇸 The single `Diagnos` `create_app` built or was given, shared by every request this process serves.

    Reading it off `request.app.state` (set once, in `create_app`) instead
    of a module-level global is what lets `conftest.py` swap in a fake
    `Diagnos` per test without any process-wide state leaking between tests.

    🇧🇷 O único `Diagnos` que `create_app` construiu ou recebeu, compartilhado
    por toda requisição que este processo serve.

    Lê-lo de `request.app.state` (setado uma vez, em `create_app`) em vez de
    um global de módulo é o que permite `conftest.py` trocar por um `Diagnos`
    falso por teste sem nenhum estado global vazar entre eles.
    """
    return cast(Diagnos, request.app.state.vault)
