"""🇺🇸 Turns CLI options into a live `Diagnos`, and renders the legacy enrollment prompt in `rich`.

`build_client` is the one seam every command calls through — and the one
seam `apps/cli/tests` monkeypatch to hand back a fake `Diagnos` that never
touches the network. The token comes from `--token`, `DIAGNOS_TOKEN`, the
system keyring (`diagnos login`) or OpenBao, in that order
(`diagnos/transport/token_sources.py`); a token taken from the environment
of an interactive terminal earns one hint towards `diagnos login`.
`enrollment_progress` only matters for the legacy `apikey-` token, whose
`unlock()` can block on a human approval in any command.

🇧🇷 Transforma opções da CLI numa `Diagnos` viva, e renderiza o prompt de enrollment legado em `rich`.

`build_client` é o único ponto por onde todo comando passa — e o único ponto
que `apps/cli/tests` faz monkeypatch para devolver uma `Diagnos` falsa que
nunca toca a rede. O token vem de `--token`, `DIAGNOS_TOKEN`, do chaveiro do
sistema (`diagnos login`) ou do OpenBao, nessa ordem
(`diagnos/transport/token_sources.py`); um token tirado do ambiente de um
terminal interativo ganha uma dica apontando para o `diagnos login`.
`enrollment_progress` só importa para o token legado `apikey-`, cujo
`unlock()` pode bloquear numa aprovação humana em qualquer comando.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from diagnos import Diagnos, EnrollmentPrompt, Settings


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


ClientFactory = Callable[[CliOptions, Callable[[EnrollmentPrompt], None] | None, bool | None], Diagnos]

# 🇺🇸 Set only inside the session agent (`agent/server.py`): every command then shares the agent's one client.
# 🇧🇷 Definido só dentro do agente de sessão (`agent/server.py`): todo comando então divide o único client do agente.
_client_factory: ClientFactory | None = None
_agent_stop_requested = False
_environment_hinted = False


def host_clients(factory: ClientFactory | None) -> None:
    """🇺🇸 Makes `build_client` hand out `factory`'s client (the agent), or builds one per command again (`None`).

    🇧🇷 Faz o `build_client` entregar o client de `factory` (o agente), ou volta a construir um por comando (`None`).
    """
    global _client_factory
    _client_factory = factory


def is_hosted() -> bool:
    """🇺🇸 Whether this command runs inside the session agent. 🇧🇷 Se este comando roda dentro do agente de sessão."""
    return _client_factory is not None


def request_agent_stop() -> None:
    """🇺🇸 Asks the agent to exit once this command's reply is sent (`logout`). 🇧🇷 Pede ao agente para sair."""
    global _agent_stop_requested
    _agent_stop_requested = True


def consume_agent_stop() -> bool:
    """🇺🇸 Whether the last command asked the agent to stop — and resets the request.

    🇧🇷 Se o último comando pediu ao agente para parar — e zera o pedido.
    """
    global _agent_stop_requested
    requested, _agent_stop_requested = _agent_stop_requested, False
    return requested


def build_client(
    options: CliOptions,
    *,
    on_prompt: Callable[[EnrollmentPrompt], None] | None = None,
    auto_unseal: bool | None = None,
) -> Diagnos:
    """🇺🇸 The `Diagnos` for this command: the session agent's when running inside it, else `make_client`'s.

    🇧🇷 A `Diagnos` deste comando: a do agente de sessão quando roda dentro dele, senão a de `make_client`.
    """
    if _client_factory is not None:
        return _client_factory(options, on_prompt, auto_unseal)
    return make_client(options, on_prompt=on_prompt, auto_unseal=auto_unseal)


def environment(options: CliOptions) -> dict[str, str]:
    """🇺🇸 The real environment with `--vault-url` on top. 🇧🇷 O ambiente de verdade com `--vault-url` por cima."""
    env = dict(os.environ)
    if options.vault_url is not None:
        env["DIAGNOS_VAULT_URL"] = options.vault_url
    return env


def make_client(
    options: CliOptions,
    *,
    on_prompt: Callable[[EnrollmentPrompt], None] | None = None,
    auto_unseal: bool | None = None,
) -> Diagnos:
    """🇺🇸 Builds a new `Diagnos`; `--token`/`--vault-url` override the real environment on top of it.

    Routing overrides through `Settings.from_env` (instead of hand-building
    a `Settings`) mirrors `client.py`'s own `_resolve_settings`: every other
    env var (`DIAGNOS_TIMEOUT_SECONDS`, `OPENBAO_*`) still applies exactly as
    it would without `--token`/`--vault-url` — a flag is choosing one token
    or endpoint, not opting out of the rest of the configuration. The CLI,
    unlike a library call on an explicit mapping, does look in the keyring.

    🇧🇷 Constrói a `Diagnos` desta invocação; `--token`/`--vault-url` sobrescrevem o ambiente de verdade.

    Rotear as sobrescritas por `Settings.from_env` (em vez de montar um
    `Settings` à mão) espelha o próprio `_resolve_settings` de `client.py`:
    toda outra variável de ambiente (`DIAGNOS_TIMEOUT_SECONDS`, `OPENBAO_*`)
    continua valendo exatamente como valeria sem `--token`/`--vault-url` —
    uma flag está escolhendo um token ou um endpoint, não saindo do resto da
    configuração. A CLI, diferente de uma chamada de biblioteca sobre um
    mapeamento explícito, procura no chaveiro.
    """
    settings = Settings.from_env(environment(options), token=options.token, keyring=True)
    vault = Diagnos(settings=settings, on_prompt=on_prompt, auto_unseal=auto_unseal)
    hint_environment_token(vault.token_source, quiet=options.quiet)
    return vault


def hint_environment_token(source: str, *, quiet: bool) -> None:
    """🇺🇸 Once per run: a token from `DIAGNOS_TOKEN` in an interactive terminal belongs in the keyring.

    `DIAGNOS_TOKEN` is how CI and containers receive a secret; on a
    workstation it sits in the shell's environment (and often its history),
    where every process the user starts can read it.

    🇧🇷 Uma vez por execução: um token de `DIAGNOS_TOKEN` num terminal interativo deveria estar no chaveiro.

    `DIAGNOS_TOKEN` é como CI e containers recebem um segredo; numa estação
    de trabalho ele fica no ambiente do shell (e muitas vezes no histórico),
    onde todo processo que a pessoa sobe consegue lê-lo.
    """
    global _environment_hinted
    if _environment_hinted or quiet or source != "DIAGNOS_TOKEN":
        return
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        return
    _environment_hinted = True
    Console(stderr=True, highlight=False).print(
        "[yellow]DIAGNOS_TOKEN is meant for CI and containers; on this machine `diagnos login` keeps the token in "
        "the system keyring (or OpenBao), out of the shell's environment.\n"
        "DIAGNOS_TOKEN é para CI e containers; nesta máquina o `diagnos login` guarda o token no chaveiro do "
        "sistema (ou no OpenBao), fora do ambiente do shell.[/yellow]"
    )


def _render_prompt_panel(console: Console, prompt: EnrollmentPrompt) -> None:
    """🇺🇸 The link and the big, spaced-out code a human types to approve this SDK session (legacy token only).

    🇧🇷 O link e o código grande, espaçado, que uma pessoa digita para aprovar esta sessão de SDK (só o legado).
    """
    spaced_code = "  ".join(prompt.code)
    body = (
        "Open this link and type the code below to approve this session.\n"
        "Abra este link e digite o código abaixo para aprovar esta sessão.\n\n"
        f"[bold cyan]{escape(prompt.approval_url)}[/bold cyan]\n\n"
        f"[bold white on grey23]  {spaced_code}  [/bold white on grey23]"
    )
    if not is_hosted():
        # 🇺🇸 Outside the agent this approval dies with the process — say how to keep it.
        # 🇧🇷 Fora do agente esta aprovação morre com o processo — diga como mantê-la.
        body += (
            "\n\n[dim]Tip: `diagnos session start` keeps the session for the next commands; a service account "
            "token (`diagnos login`) needs no approval at all.\n"
            "Dica: `diagnos session start` mantém a sessão para os próximos comandos; um token de conta de serviço "
            "(`diagnos login`) não precisa de aprovação nenhuma.[/dim]"
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
