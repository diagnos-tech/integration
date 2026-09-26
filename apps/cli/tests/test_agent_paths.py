"""🇺🇸 Where the agent's socket lives: enabled or not, idle timeout, a private directory, one socket per identity.

🇧🇷 Onde fica o socket do agente: ligado ou não, tempo ocioso, um diretório privado, um socket por identidade.
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
from pathlib import Path

import pytest
from diagnos_cli.agent.paths import (
    DEFAULT_IDLE_MINUTES,
    AgentUnavailable,
    agent_enabled,
    identity,
    idle_seconds,
    runtime_dir,
    socket_path,
)


@pytest.mark.parametrize(
    ("value", "enabled"),
    [
        (None, True),
        ("1", True),
        ("on", True),
        ("off", False),
        ("OFF ", False),
        ("0", False),
        ("false", False),
        ("no", False),
    ],
)
def test_agent_enabled_unless_switched_off(value: str | None, enabled: bool) -> None:
    """🇺🇸 On by default on POSIX; `DIAGNOS_AGENT=off` (any case, any spacing) and friends switch it off.

    🇧🇷 Ligado por padrão em POSIX; `DIAGNOS_AGENT=off` (qualquer caixa, qualquer espaço) e afins o desligam.
    """
    env = {} if value is None else {"DIAGNOS_AGENT": value}
    assert agent_enabled(env) is enabled


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        (None, DEFAULT_IDLE_MINUTES * 60),
        ("30", 1800),
        ("0.5", 30),
        ("abc", DEFAULT_IDLE_MINUTES * 60),
        ("0", DEFAULT_IDLE_MINUTES * 60),
        ("-5", DEFAULT_IDLE_MINUTES * 60),
    ],
)
def test_idle_seconds(value: str | None, seconds: float) -> None:
    """🇺🇸 Minutes from the environment; anything unusable keeps the 8-hour default.

    🇧🇷 Minutos do ambiente; qualquer coisa inutilizável mantém o padrão de 8 horas.
    """
    env = {} if value is None else {"DIAGNOS_AGENT_IDLE_MINUTES": value}
    assert idle_seconds(env) == seconds


def test_runtime_dir_is_created_private_under_xdg(tmp_path: Path) -> None:
    """🇺🇸 `$XDG_RUNTIME_DIR/diagnos-<uid>`, mode `0700`, and a second call accepts what the first made.

    🇧🇷 `$XDG_RUNTIME_DIR/diagnos-<uid>`, modo `0700`, e uma segunda chamada aceita o que a primeira criou.
    """
    env = {"XDG_RUNTIME_DIR": str(tmp_path)}
    directory = runtime_dir(env)
    assert directory == tmp_path / f"diagnos-{os.getuid()}"
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert runtime_dir(env) == directory


def test_runtime_dir_falls_back_to_the_temp_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """🇺🇸 Without `XDG_RUNTIME_DIR` (macOS, containers), the per-user temp dir holds it.

    🇧🇷 Sem `XDG_RUNTIME_DIR` (macOS, contêineres), o temp do usuário o guarda.
    """
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    assert runtime_dir({}).parent == tmp_path


def test_runtime_dir_refuses_a_directory_others_can_enter(tmp_path: Path) -> None:
    """🇺🇸 A pre-existing `0755` directory is refused, not repaired — someone else may have prepared it.

    🇧🇷 Um diretório `0755` já existente é recusado, não consertado — outra pessoa pode tê-lo preparado.
    """
    loose = tmp_path / f"diagnos-{os.getuid()}"
    loose.mkdir()
    loose.chmod(0o755)
    with pytest.raises(AgentUnavailable, match="0700"):
        runtime_dir({"XDG_RUNTIME_DIR": str(tmp_path)})
    assert stat.S_IMODE(loose.stat().st_mode) == 0o755


def test_runtime_dir_refuses_a_symlink(tmp_path: Path) -> None:
    """🇺🇸 A symlink in its place is refused even when it points at a private directory.

    🇧🇷 Um symlink no lugar é recusado mesmo apontando para um diretório privado.
    """
    target = tmp_path / "elsewhere"
    target.mkdir(mode=0o700)
    (tmp_path / f"diagnos-{os.getuid()}").symlink_to(target)
    with pytest.raises(AgentUnavailable):
        runtime_dir({"XDG_RUNTIME_DIR": str(tmp_path)})


def test_identity_prefers_flags_then_environment_then_the_default_vault() -> None:
    """🇺🇸 Same precedence as every command: `--token`/`--vault-url`, then the environment, then the default.

    🇧🇷 A mesma precedência de todo comando: `--token`/`--vault-url`, depois o ambiente, depois o padrão.
    """
    env = {"DIAGNOS_API_TOKEN": "env-token", "DIAGNOS_VAULT_URL": "https://env.example"}
    assert identity(env, "flag-token", "https://flag.example") == ("https://flag.example", "flag-token")
    assert identity(env, None, None) == ("https://env.example", "env-token")
    assert identity({"DIAGNOS_API_TOKEN": "t"}, None, None) == ("https://vault.diagnos.health", "t")
    assert identity({}, None, "https://x.example") is None


def test_socket_path_is_one_per_identity_and_never_names_the_token(tmp_path: Path) -> None:
    """🇺🇸 A hash names the socket: stable for one identity, different for another, the token nowhere in it.

    🇧🇷 Um hash nomeia o socket: estável para uma identidade, diferente para outra, o token em lugar nenhum.
    """
    env = {"XDG_RUNTIME_DIR": str(tmp_path)}
    mine = socket_path(env, ("https://vault.diagnos.health", "secret-token"))
    assert re.fullmatch(r"agent-[0-9a-f]{16}\.sock", mine.name)
    assert "secret-token" not in str(mine)
    assert mine == socket_path(env, ("https://vault.diagnos.health", "secret-token"))
    assert mine != socket_path(env, ("https://vault.diagnos.health", "other-token"))
    assert mine != socket_path(env, ("https://staging.example", "secret-token"))
    assert mine.parent == runtime_dir(env)
