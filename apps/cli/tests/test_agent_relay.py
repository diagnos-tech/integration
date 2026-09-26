"""🇺🇸 The agent end to end: real socket, real server, real CLI — one session shared by every command.

🇧🇷 O agente de ponta a ponta: socket de verdade, servidor de verdade, CLI de verdade — uma sessão para todo comando.
"""

from __future__ import annotations

import json
import os
import socket
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from diagnos import EnrollmentPrompt
from diagnos_cli import context
from diagnos_cli.agent import client, protocol
from diagnos_cli.exit_codes import EXIT_NOT_FOUND
from diagnos_cli.main import run

from .agent_harness import running_agent, socket_directory
from .conftest import FakeDiagnos

PROMPT = EnrollmentPrompt(
    enrollment_id="enr_1", approval_url="https://app.diagnos.health/approve/enr_1", code="K7Q2", expires_at=0
)


class PromptingVault(FakeDiagnos):
    """🇺🇸 A fake whose first `unlock()` asks a human, like a real enrollment.

    🇧🇷 Um fake cujo primeiro `unlock()` pede a uma pessoa, como um enrollment de verdade.
    """

    def __init__(self) -> None:
        """🇺🇸 No prompt callback yet. 🇧🇷 Sem callback de prompt ainda."""
        super().__init__()
        self.on_prompt: Callable[[EnrollmentPrompt], None] | None = None
        self.enrollments = 0

    def bind_prompt(self, on_prompt: Callable[[EnrollmentPrompt], None] | None) -> None:
        """🇺🇸 What `make_client(on_prompt=…)` received. 🇧🇷 O que `make_client(on_prompt=…)` recebeu."""
        self.on_prompt = on_prompt

    def unlock(self) -> Any:
        if not self._unlocked:
            self.enrollments += 1
            if self.on_prompt is not None:
                self.on_prompt(PROMPT)
        return super().unlock()


def test_every_command_shares_one_client_and_one_enrollment() -> None:
    """🇺🇸 `login`, then two more commands: one client built, one enrollment, one panel.

    🇧🇷 `login`, depois mais dois comandos: um client construído, um enrollment, um painel.
    """
    vault = PromptingVault()
    with running_agent(vault) as agent:
        code, out, err = agent.run(["login"])
        assert code == 0
        assert "Kept in memory by the diagnos agent" in out
        assert PROMPT.approval_url in err
        assert "Tip:" not in err
        for _ in range(2):
            code, out, err = agent.run(["groups"])
            assert (code, out, err) == (0, "sg_oncology\n", "")
        assert len(agent.clients_made) == 1
        assert vault.enrollments == 1


def test_json_output_reaches_stdout_untouched() -> None:
    """🇺🇸 `--json` output arrives byte for byte, ready for `jq`. 🇧🇷 A saída `--json` chega intacta, pronta p/ `jq`."""
    with running_agent(FakeDiagnos()) as agent:
        code, out, err = agent.run(["--json", "groups"])
    assert code == 0
    assert json.loads(out) == {"security_groups": ["sg_oncology"]}
    assert err == ""


def test_a_failing_command_keeps_its_exit_code_and_message() -> None:
    """🇺🇸 Exit codes and error messages cross the socket unchanged. 🇧🇷 Códigos e mensagens de erro chegam intactos."""
    with running_agent(FakeDiagnos()) as agent:
        code, out, err = agent.run(["patients", "get", "missing"])
    assert code == EXIT_NOT_FOUND
    assert out == ""
    assert "Not found" in err


@pytest.mark.parametrize(("answer", "deleted"), [("y\n", True), ("n\n", False)])
def test_confirmation_prompts_read_the_callers_stdin(answer: str, deleted: bool) -> None:
    """🇺🇸 `patients delete` asks on the caller's terminal and honors the answer.

    🇧🇷 `patients delete` pergunta no terminal de quem chamou e respeita a resposta.
    """
    with running_agent(FakeDiagnos()) as agent:
        code, out, _err = agent.run(["patients", "delete", "pat_1"], stdin=answer)
        reached_the_vault = bool(agent.clients_made)
    assert code == 0
    assert "Move patient pat_1 to the trash?" in out
    assert reached_the_vault is deleted


def test_a_prompt_with_no_input_aborts() -> None:
    """🇺🇸 A closed stdin (a script without `--yes`) aborts instead of hanging.

    🇧🇷 Um stdin fechado (um script sem `--yes`) aborta em vez de travar.
    """
    with running_agent(FakeDiagnos()) as agent:
        code, _out, err = agent.run(["patients", "delete", "pat_1"])
        assert agent.clients_made == []
    assert code == 1
    assert "Aborted" in err


def test_relative_paths_resolve_in_the_callers_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """🇺🇸 `-o out.dcm` lands where the caller ran the command, not where the agent started.

    🇧🇷 `-o out.dcm` cai onde quem chamou rodou o comando, não onde o agente subiu.
    """
    monkeypatch.chdir(tmp_path)
    with running_agent(FakeDiagnos()) as agent:
        code, _out, _err = agent.run(["-q", "files", "download", "node_1", "-o", "out.dcm"])
    assert code == 0
    assert (tmp_path / "out.dcm").read_bytes() == b"fake-encrypted-then-decrypted-bytes"


def test_only_presentation_variables_cross_and_only_for_one_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `DIAGNOS_GROUP` and `NO_COLOR` apply to the one command; a token or vault URL from the caller never does.

    🇧🇷 `DIAGNOS_GROUP` e `NO_COLOR` valem para aquele comando; um token ou URL de cofre de quem chama, nunca.
    """
    monkeypatch.delenv("DIAGNOS_GROUP", raising=False)
    seen: list[dict[str, str | None]] = []

    def record(argv: list[str]) -> int:
        seen.append({key: os.environ.get(key) for key in ("DIAGNOS_GROUP", "NO_COLOR", "DIAGNOS_API_TOKEN")})
        return run(argv)

    caller_env = {"DIAGNOS_GROUP": "sg_cardio", "NO_COLOR": "1", "DIAGNOS_API_TOKEN": "someone-elses"}
    with running_agent(FakeDiagnos(), run_cli=record) as agent:
        agent.run(["groups"], env=caller_env)
        agent.run(["groups"])
    assert seen[0] == {
        "DIAGNOS_GROUP": "sg_cardio",
        "NO_COLOR": "1",
        "DIAGNOS_API_TOKEN": os.environ.get("DIAGNOS_API_TOKEN"),
    }
    assert seen[1]["DIAGNOS_GROUP"] is None
    assert "DIAGNOS_GROUP" not in os.environ


def test_the_group_default_from_the_callers_environment_is_used() -> None:
    """🇺🇸 `DIAGNOS_GROUP` in the caller's shell picks the group for a write run by the agent.

    🇧🇷 `DIAGNOS_GROUP` no shell de quem chama escolhe o grupo de uma escrita rodada pelo agente.
    """
    vault = FakeDiagnos()
    vault.granted_groups = ["sg_oncology", "sg_cardio"]
    with running_agent(vault) as agent:
        code, _out, err = agent.run(
            ["patients", "create", "--legal-name", "Ana", "--display-name", "Ana"], env={"DIAGNOS_GROUP": "sg_cardio"}
        )
    assert code == 0, err
    assert next(kwargs for name, kwargs in vault.patients.calls if name == "create")["security_group"] == "sg_cardio"


def test_logout_locks_once_wipes_and_stops() -> None:
    """🇺🇸 `logout` revokes the session, closes the client, removes the socket and ends the agent.

    🇧🇷 `logout` revoga a sessão, fecha o client, remove o socket e encerra o agente.
    """
    vault = FakeDiagnos()
    with running_agent(vault) as agent:
        agent.run(["groups"])
        code, out, _err = agent.run(["logout"])
        assert code == 0
        assert "Logged out" in out
        assert (vault.lock_calls, vault.close_calls) == (1, 1)
        assert agent.stopped()
        assert not agent.path.exists()
        assert client.connect(agent.path) is None


def test_logout_as_json() -> None:
    """🇺🇸 `--json logout` says whether a kept session was ended. 🇧🇷 `--json logout` diz se uma sessão foi encerrada."""
    with running_agent(FakeDiagnos()) as agent:
        _code, out, _err = agent.run(["--json", "logout"])
    assert json.loads(out) == {"logged_out": True}


def test_logout_before_any_command_still_stops() -> None:
    """🇺🇸 Nothing to lock yet, but the agent still goes away. 🇧🇷 Nada a travar ainda, mas o agente sai mesmo assim."""
    vault = FakeDiagnos()
    with running_agent(vault) as agent:
        agent.run(["logout"])
        assert agent.stopped()
    assert vault.lock_calls == 0


def test_idle_timeout_locks_and_exits() -> None:
    """🇺🇸 After the idle timeout with no command, the session is revoked and the agent exits.

    🇧🇷 Depois do tempo ocioso sem comando, a sessão é revogada e o agente sai.
    """
    vault = FakeDiagnos()
    with running_agent(vault, idle_seconds=0.3) as agent:
        agent.run(["groups"])
        assert agent.stopped(timeout=5)
        assert not agent.path.exists()
    assert (vault.lock_calls, vault.close_calls) == (1, 1)


def test_an_unreachable_vault_on_the_way_out_still_wipes_keys() -> None:
    """🇺🇸 `lock()` failing (vault down) never skips `close()`. 🇧🇷 `lock()` falhando (cofre fora) não pula `close()`."""

    class Offline(FakeDiagnos):
        def lock(self) -> None:
            raise ConnectionError("vault unreachable")

    vault = Offline()
    with running_agent(vault) as agent:
        agent.run(["groups"])
        agent.run(["logout"])
        assert agent.stopped()
    assert vault.close_calls == 1


def test_another_users_connection_is_turned_away() -> None:
    """🇺🇸 A peer with another uid gets nothing and the agent keeps serving its owner.

    🇧🇷 Um par com outro uid não recebe nada e o agente continua servindo o dono.
    """
    uids = [os.getuid() + 1]

    def uid_of(conn: socket.socket) -> int | None:
        return uids.pop() if uids else os.getuid()

    vault = FakeDiagnos()
    with running_agent(vault, uid_of=uid_of) as agent:
        code, out, err = agent.run(["groups"])
        assert (code, out) == (1, "")
        assert "stopped mid-command" in err
        assert agent.run(["groups"])[0] == 0
    assert vault.security_groups == []


def test_ping_reports_the_session() -> None:
    """🇺🇸 `ping` shows pid and whether a session is kept, and never unlocks by itself.

    🇧🇷 `ping` mostra o pid e se há sessão guardada, e nunca desbloqueia sozinho.
    """
    with running_agent(FakeDiagnos()) as agent:
        before = client.ping(agent.path)
        agent.run(["groups"])
        after = client.ping(agent.path)
    assert before is not None and after is not None
    assert before["type"] == "pong"
    assert before["pid"] == os.getpid()
    assert (before["unlocked"], before["groups"]) == (False, [])
    assert (after["unlocked"], after["groups"]) == (True, ["sg_oncology"])


def test_a_crashing_command_exits_1_and_the_agent_survives() -> None:
    """🇺🇸 An unexpected exception is exit code 1 for that command only; the session stays.

    🇧🇷 Uma exceção inesperada é código 1 só para aquele comando; a sessão fica.
    """

    def flaky(argv: list[str]) -> int:
        if argv == ["boom"]:
            raise RuntimeError("bug")
        return run(argv)

    with running_agent(FakeDiagnos(), run_cli=flaky) as agent:
        assert agent.run(["boom"])[0] == 1
        assert agent.run(["groups"])[0] == 0
        assert len(agent.clients_made) == 1


@pytest.mark.parametrize("garbage", [b"not json\n", b'{"type":"stop"}\n', b"", b'{"type":"run","argv":"x"}'])
def test_malformed_requests_are_dropped(garbage: bytes) -> None:
    """🇺🇸 Garbage, unknown frame types and half requests close that connection only.

    🇧🇷 Lixo, tipos de frame desconhecidos e requisições pela metade fecham só aquela conexão.
    """
    with running_agent(FakeDiagnos()) as agent:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as raw:
            raw.connect(str(agent.path))
            raw.sendall(garbage)
            raw.shutdown(socket.SHUT_WR)
            protocol.Reader(raw).next()
        assert agent.run(["groups"])[0] == 0


def test_a_client_that_leaves_mid_command_does_not_stop_the_agent() -> None:
    """🇺🇸 Ctrl-C on a prompt: the caller vanishes, the command sees end of input, the agent carries on.

    🇧🇷 Ctrl-C num prompt: quem chamou some, o comando vê fim de entrada, o agente segue.
    """
    with running_agent(FakeDiagnos()) as agent:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as raw:
            raw.connect(str(agent.path))
            protocol.send(raw, {"type": "run", "argv": ["patients", "delete", "pat_1"], "cwd": "/", "env": {}})
            reader = protocol.Reader(raw)
            while (frame := reader.next()) is not None and frame["type"] != "prompt":
                pass
        assert agent.run(["groups"])[0] == 0


def test_the_socket_is_private_and_replaces_a_stale_one() -> None:
    """🇺🇸 A leftover file at the path (a crashed agent) is replaced; the new socket is `0600`.

    🇧🇷 Um arquivo que sobrou no caminho (um agente que caiu) é substituído; o socket novo é `0600`.
    """
    with socket_directory() as directory:
        stale = directory / "agent.sock"
        stale.write_text("left over")
        with running_agent(FakeDiagnos(), path=stale) as agent:
            info = agent.path.lstat()
            assert stat.S_ISSOCK(info.st_mode)
            assert stat.S_IMODE(info.st_mode) == 0o600
            assert agent.run(["groups"])[0] == 0


def test_the_hosting_seam_is_removed_when_the_agent_stops() -> None:
    """🇺🇸 After the agent, `build_client` goes back to building its own client.

    🇧🇷 Depois do agente, o `build_client` volta a construir o próprio client.
    """
    with running_agent(FakeDiagnos()) as agent:
        assert context.is_hosted()
        agent.run(["logout"])
        assert agent.stopped()
    assert not context.is_hosted()
    assert context.consume_agent_stop() is False
