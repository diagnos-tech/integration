"""🇺🇸 Turns CLI options into a live `Diagnos`, and renders the enrollment prompt in `rich`.

`build_client` is the one seam every command calls through — and the one
seam `apps/cli/tests` monkeypatch to hand back a fake `Diagnos` that never
touches the network. `enrollment_progress` exists because enrollment is not
only `login`'s problem: `unlock()` is lazy (`apps/sdk/README.md`), so *any*
command's first resource access can block on a human approval, and every
one of them deserves the same rich panel and spinner, not just `login`.

🇧🇷 Transforma opções da CLI numa `Diagnos` viva, e renderiza o prompt de
enrollment em `rich`.

`build_client` é o único ponto por onde todo comando passa — e o único
ponto que `apps/cli/tests` faz monkeypatch para devolver uma `Diagnos` falsa que
nunca toca a rede. `enrollment_progress` existe porque enrollment não é só
problema do `login`: `unlock()` é preguiçoso (`apps/sdk/README.md`), então o
primeiro acesso a um recurso de *qualquer* comando pode bloquear numa
aprovação humana, e todos merecem o mesmo painel rich e o mesmo spinner, não
só o `login`.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from diagnos import Diagnos, EnrollmentPrompt, Settings
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel


@dataclass(frozen=True)
class CliOptions:
    """🇺🇸 The root `--json`/`--quiet`/`--vault-url`/`--token`/`--no-color` options, threaded through every command.

    🇧🇷 As opções de raiz `--json`/`--quiet`/`--vault-url`/`--token`/`--no-color`, passadas por todo comando.
    """

    json_output: bool = False
    quiet: bool = False
    vault_url: str | None = None
    token: str | None = None
    no_color: bool = False


def build_client(
    options: CliOptions,
    *,
    on_prompt: Callable[[EnrollmentPrompt], None] | None = None,
    auto_unseal: bool | None = None,
) -> Diagnos:
    """🇺🇸 Builds the `Diagnos` for this invocation; `--token`/`--vault-url` override the real environment on top of it.

    Routing overrides through `Settings.from_env` (instead of hand-building
    a `Settings`) mirrors `client.py`'s own `_resolve_settings`: every other
    env var (`DIAGNOS_TIMEOUT_SECONDS`, `OPENBAO_*`) still applies exactly as
    it would without `--token`/`--vault-url` — a flag is choosing one
    credential or endpoint, not opting out of the rest of the configuration.

    🇧🇷 Constrói a `Diagnos` desta invocação; `--token`/`--vault-url`
    sobrescrevem o ambiente de verdade por cima dele.

    Rotear as sobrescritas por `Settings.from_env` (em vez de montar um
    `Settings` à mão) espelha o próprio `_resolve_settings` de `client.py`:
    toda outra variável de ambiente (`DIAGNOS_TIMEOUT_SECONDS`,
    `OPENBAO_*`) continua valendo exatamente como valeria sem
    `--token`/`--vault-url` — uma flag está escolhendo uma credencial ou um
    endpoint, não saindo do resto da configuração.
    """
    env = dict(os.environ)
    if options.token is not None:
        env["DIAGNOS_API_TOKEN"] = options.token
    if options.vault_url is not None:
        env["DIAGNOS_VAULT_URL"] = options.vault_url
    settings = Settings.from_env(env)
    return Diagnos(settings=settings, on_prompt=on_prompt, auto_unseal=auto_unseal)


def _render_prompt_panel(console: Console, prompt: EnrollmentPrompt) -> None:
    """🇺🇸 The link and the big, spaced-out code a human types to approve this SDK session.

    🇧🇷 O link e o código grande, espaçado, que uma pessoa digita para aprovar esta sessão de SDK.
    """
    spaced_code = "  ".join(prompt.code)
    body = (
        "Open this link and type the code below to approve this session.\n"
        "Abra este link e digite o código abaixo para aprovar esta sessão.\n\n"
        f"[bold cyan]{escape(prompt.approval_url)}[/bold cyan]\n\n"
        f"[bold white on grey23]  {spaced_code}  [/bold white on grey23]"
    )
    console.print(Panel(body, title="diagnos · enrollment", expand=False))


@contextmanager
def enrollment_progress(console: Console, *, quiet: bool) -> Iterator[Callable[[EnrollmentPrompt], None]]:
    """🇺🇸 Yields an `on_prompt` that shows the panel, then a spinner until the `with` block exits.

    `enroll()` (`session/enrollment.py`) calls `on_prompt` exactly once,
    before its own blocking poll loop — there is no later callback to say
    "approved" or "denied". So the spinner is started here, inside
    `on_prompt`, and stopped in `finally` once whatever blocked on approval
    (`unlock()`, or a lazy resource access) has returned control to us.

    🇧🇷 Devolve um `on_prompt` que mostra o painel, depois um spinner até o
    bloco `with` terminar.

    `enroll()` (`session/enrollment.py`) chama `on_prompt` uma única vez,
    antes do próprio laço de poll bloqueante — não existe um callback
    depois para dizer "aprovado" ou "negado". Então o spinner é iniciado
    aqui, dentro de `on_prompt`, e parado no `finally` assim que o que
    bloqueou esperando aprovação (`unlock()`, ou um acesso preguiçoso a
    recurso) devolveu o controle para nós.
    """
    live_status = console.status("[cyan]waiting for approval… · aguardando aprovação…[/cyan]", spinner="dots")
    started = False

    def on_prompt(prompt: EnrollmentPrompt) -> None:
        """🇺🇸 Show the link and code once, then hand control back to the spinner.

        🇧🇷 Mostra link e código uma vez e devolve o controle ao spinner.
        """
        nonlocal started
        _render_prompt_panel(console, prompt)
        if not quiet:
            live_status.start()
            started = True

    try:
        yield on_prompt
    finally:
        if started:
            live_status.stop()
