"""🇺🇸 The agent's one `Diagnos`: built on the first command, reused by every later one, wiped on the way out.

🇧🇷 A única `Diagnos` do agente: construída no primeiro comando, reusada por todos os seguintes, apagada na saída.
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Callable
from typing import Any

from diagnos import Diagnos, EnrollmentPrompt

from diagnos_cli import context
from diagnos_cli.context import CliOptions


class SessionHost:
    """🇺🇸 Owns the agent's one `Diagnos` and routes its enrollment prompt to whichever command is running.

    🇧🇷 Dono da única `Diagnos` do agente, e roteia o prompt de enrollment para o comando que estiver rodando.
    """

    def __init__(self, make_client: Callable[..., Diagnos] = context.make_client) -> None:
        """🇺🇸 `make_client` builds the real client on the first command. 🇧🇷 `make_client` constrói o client real."""
        self._make_client = make_client
        self._vault: Diagnos | None = None
        self._prompt: Callable[[EnrollmentPrompt], None] | None = None
        self.started_at = time.time()

    def client_for(
        self,
        options: CliOptions,
        on_prompt: Callable[[EnrollmentPrompt], None] | None,
        auto_unseal: bool | None,
    ) -> Diagnos:
        """🇺🇸 `context.build_client` inside the agent: always the same client, whatever the command.

        🇧🇷 O `context.build_client` dentro do agente: sempre o mesmo client, seja qual for o comando.
        """
        self._prompt = on_prompt
        if self._vault is None:
            self._vault = self._make_client(options, on_prompt=self._relay_prompt, auto_unseal=auto_unseal)
        return self._vault

    def _relay_prompt(self, prompt: EnrollmentPrompt) -> None:
        """🇺🇸 A (re-)enrollment shows its link on the terminal of the command that triggered it.

        🇧🇷 Um (re)enrollment mostra o link no terminal do comando que o disparou.
        """
        if self._prompt is not None:
            self._prompt(prompt)

    def end_command(self) -> None:
        """🇺🇸 Forgets the finished command's prompt callback. 🇧🇷 Esquece o callback de prompt do comando que acabou."""
        self._prompt = None

    def status(self) -> dict[str, Any]:
        """🇺🇸 What `diagnos status` shows about this agent. 🇧🇷 O que o `diagnos status` mostra sobre este agente."""
        groups = self._vault.security_groups if self._vault is not None else []
        return {"pid": os.getpid(), "started_at": int(self.started_at), "unlocked": bool(groups), "groups": groups}

    def shutdown(self) -> None:
        """🇺🇸 Revokes the session and wipes its keys — an agent never leaves a live session behind.

        🇧🇷 Revoga a sessão e apaga as chaves — um agente nunca deixa uma sessão viva para trás.
        """
        if self._vault is None:
            return
        try:
            # 🇺🇸 Best effort on the way out: an unreachable vault must not keep the keys alive in memory.
            # 🇧🇷 Melhor esforço na saída: um cofre inalcançável não pode manter as chaves vivas na memória.
            with contextlib.suppress(Exception):
                self._vault.lock()
        finally:
            self._vault.close()
            self._vault = None
