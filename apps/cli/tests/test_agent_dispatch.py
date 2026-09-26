"""🇺🇸 Which commands go to the agent, which stay here, and a real detached agent started and stopped.

🇧🇷 Quais comandos vão para o agente, quais ficam aqui, e um agente destacado de verdade subindo e parando.
"""

from __future__ import annotations

import io
import os
import signal
import time
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from diagnos_cli.agent import client
from diagnos_cli.agent import dispatch as dispatch_module
from diagnos_cli.agent.dispatch import agent_status, dispatch
from diagnos_cli.agent.paths import AgentUnavailable, identity, socket_path

from .agent_harness import RunningAgent, running_agent, socket_directory
from .conftest import FakeDiagnos

TOKEN = "tok_test"  # noqa: S105 — a fake token that only names a test socket
VAULT = "https://vault.example"


@pytest.fixture
def env() -> Iterator[dict[str, str]]:
    """🇺🇸 An agent-enabled environment with a token, sockets under a short private directory.

    🇧🇷 Um ambiente com o agente ligado e um token, sockets num diretório curto e privado.
    """
    with socket_directory() as directory:
        yield {"XDG_RUNTIME_DIR": str(directory), "DIAGNOS_API_TOKEN": TOKEN, "DIAGNOS_VAULT_URL": VAULT}


def _call(argv: list[str], env: dict[str, str], stdin: str = "") -> tuple[int | None, str, str]:
    """🇺🇸 `dispatch` with captured streams. 🇧🇷 `dispatch` com os fluxos capturados."""
    out, err = io.StringIO(), io.StringIO()
    code = dispatch(argv, env=env, stdin=io.StringIO(stdin), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def _agent_for(env: dict[str, str], stack: ExitStack, token: str | None = None) -> RunningAgent:
    """🇺🇸 A harness agent listening where `dispatch` will look for this identity.

    🇧🇷 Um agente do harness escutando onde o `dispatch` vai procurar esta identidade.
    """
    who = identity(env, token, None)
    assert who is not None
    return stack.enter_context(running_agent(FakeDiagnos(), path=socket_path(env, who)))


@pytest.mark.parametrize(
    "argv",
    [["--help"], ["groups", "--help"], ["--version"], [], ["--json"], ["no-such-command"], ["status"]],
    ids=["help", "sub-help", "version", "bare", "only-flags", "unknown", "plain-status"],
)
def test_runs_here_when_the_session_is_not_needed(env: dict[str, str], argv: list[str]) -> None:
    """🇺🇸 Help, version, a plain `status` and anything unknown never reach an agent.

    🇧🇷 Ajuda, versão, um `status` simples e qualquer coisa desconhecida nunca chegam a um agente.
    """
    with ExitStack() as stack:
        agent = _agent_for(env, stack)
        assert _call(argv, env)[0] is None
        assert agent.clients_made == []


def test_runs_here_when_switched_off_or_without_a_token(env: dict[str, str]) -> None:
    """🇺🇸 `DIAGNOS_AGENT=off`, or no token at all, keeps the command in this process.

    🇧🇷 `DIAGNOS_AGENT=off`, ou nenhum token, mantém o comando neste processo.
    """
    with ExitStack() as stack:
        _agent_for(env, stack)
        assert _call(["groups"], {**env, "DIAGNOS_AGENT": "off"})[0] is None
        no_token = {key: value for key, value in env.items() if key != "DIAGNOS_API_TOKEN"}
        assert _call(["groups"], no_token)[0] is None


def test_runs_here_when_no_agent_is_running(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Without an agent, only `login` starts one — any other command just runs here.

    🇧🇷 Sem agente, só o `login` sobe um — qualquer outro comando só roda aqui.
    """
    monkeypatch.setattr(dispatch_module, "start", lambda *a, **k: pytest.fail("started · subiu"))
    assert _call(["groups"], env)[0] is None
    assert _call(["status", "--check"], env)[0] is None


def test_a_running_agent_runs_session_commands(env: dict[str, str]) -> None:
    """🇺🇸 With an agent up for this identity, its output and exit code are the command's.

    🇧🇷 Com um agente no ar para esta identidade, a saída e o código de saída dele são os do comando.
    """
    with ExitStack() as stack:
        agent = _agent_for(env, stack)
        assert _call(["groups"], env) == (0, "sg_oncology\n", "")
        assert _call(["--json", "status", "--check"], env)[0] == 0
        assert len(agent.clients_made) == 1


def test_another_token_reaches_another_agent(env: dict[str, str]) -> None:
    """🇺🇸 `--token` (either spelling) picks the agent of that identity — never borrows this one's session.

    🇧🇷 `--token` (qualquer grafia) escolhe o agente daquela identidade — nunca empresta a sessão deste.
    """
    with ExitStack() as stack:
        _agent_for(env, stack)
        assert _call(["--token", "someone-else", "groups"], env)[0] is None
        assert _call(["--token=someone-else", "groups"], env)[0] is None
    # 🇺🇸 One in-process agent at a time: the hosting seam is process-wide, as it is in a real agent.
    # 🇧🇷 Um agente no processo por vez: a costura de hospedagem é do processo inteiro, como num agente real.
    with ExitStack() as stack:
        _agent_for(env, stack, token="someone-else")  # noqa: S106 — a fake token
        assert _call(["--token=someone-else", "groups"], env)[0] == 0
        assert _call(["groups"], env)[0] is None


def test_login_starts_an_agent_with_the_resolved_identity(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `login` starts the agent for exactly the vault and token it resolved, then runs inside it.

    🇧🇷 O `login` sobe o agente para exatamente o cofre e o token que resolveu, depois roda dentro dele.
    """
    started: list[dict[str, Any]] = []
    with ExitStack() as stack:

        def fake_start(path: Path, child_env: dict[str, str], *, idle_seconds: float) -> None:
            started.append({"path": path, "env": child_env, "idle": idle_seconds})
            stack.enter_context(running_agent(FakeDiagnos(), path=path))

        monkeypatch.setattr(dispatch_module, "start", fake_start)
        code, out, _err = _call(
            ["--vault-url", "https://other.example", "login"], {**env, "DIAGNOS_AGENT_IDLE_MINUTES": "5"}
        )
    assert code == 0
    assert "Kept in memory by the diagnos agent" in out
    assert started[0]["env"]["DIAGNOS_VAULT_URL"] == "https://other.example"
    assert started[0]["env"]["DIAGNOS_API_TOKEN"] == TOKEN
    assert started[0]["idle"] == 300


def test_login_says_why_it_could_not_start_and_runs_here(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 An agent that cannot start is not fatal: `login` explains and runs in-process.

    🇧🇷 Um agente que não sobe não é fatal: o `login` explica e roda no próprio processo.
    """

    def fail(*args: object, **kwargs: object) -> None:
        raise AgentUnavailable("no agent today")

    monkeypatch.setattr(dispatch_module, "start", fail)
    code, _out, err = _call(["login"], env)
    assert code is None
    assert "no agent today" in err


def test_an_unsafe_runtime_directory_quietly_runs_here(env: dict[str, str]) -> None:
    """🇺🇸 A socket directory others can enter is never used; commands other than `login` say nothing.

    🇧🇷 Um diretório de socket em que outros entram nunca é usado; comandos além do `login` não dizem nada.
    """
    loose = Path(env["XDG_RUNTIME_DIR"]) / f"diagnos-{os.getuid()}"
    loose.mkdir(mode=0o755)
    loose.chmod(0o755)
    assert _call(["groups"], env) == (None, "", "")
    assert agent_status(env, None, None) is None


def test_agent_status(env: dict[str, str]) -> None:
    """🇺🇸 `agent_status` pings this identity's agent, and is `None` when there is none or it is off.

    🇧🇷 O `agent_status` pinga o agente desta identidade, e é `None` quando não há um ou está desligado.
    """
    assert agent_status(env, None, None) is None
    with ExitStack() as stack:
        _agent_for(env, stack)
        found = agent_status(env, None, None)
        assert found is not None and found["type"] == "pong"
        assert agent_status({**env, "DIAGNOS_AGENT": "off"}, None, None) is None
        assert agent_status(env, "someone-else", None) is None
    assert agent_status({"XDG_RUNTIME_DIR": env["XDG_RUNTIME_DIR"]}, None, None) is None


def test_a_real_detached_agent_starts_answers_and_stops_on_sigterm(env: dict[str, str]) -> None:
    """🇺🇸 `client.start` spawns `python -m diagnos_cli.agent`; `SIGTERM` removes its socket on the way out.

    Nothing here reaches a vault: the SDK client is only built by the first
    command, and this test only pings.

    🇧🇷 `client.start` sobe `python -m diagnos_cli.agent`; o `SIGTERM` remove o socket na saída.

    Nada aqui chega a um cofre: o client do SDK só é construído pelo primeiro
    comando, e este teste só pinga.
    """
    who = identity(env, None, None)
    assert who is not None
    path = socket_path(env, who)
    client.start(path, {**os.environ, **env}, idle_seconds=60)
    pong = client.ping(path)
    assert pong is not None
    assert (pong["unlocked"], pong["pid"] != os.getpid()) == (False, True)
    os.kill(int(pong["pid"]), signal.SIGTERM)
    deadline = time.monotonic() + 10
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not path.exists()
