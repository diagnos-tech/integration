"""🇺🇸 Finding `uv`, Docker and cosign: absolute `PATH` entries only, a running Docker engine, clear messages.

🇧🇷 Achar `uv`, Docker e cosign: só entradas absolutas do `PATH`, um motor Docker rodando, mensagens claras.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from diagnos._wrapper.output import Output
from diagnos._wrapper.setup.tools import INSTALL_PAGES, docker_running, find, found, missing

from conftest import Programs

_UV = "uv.exe" if os.name == "nt" else "uv"


def _executable(folder: Path, mode: int = 0o755) -> Path:
    """🇺🇸 A fake `uv` in `folder`. 🇧🇷 Um `uv` falso em `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _UV
    path.write_text("")
    path.chmod(mode)
    return path


def test_find_returns_the_first_absolute_match(tmp_path: Path) -> None:
    """🇺🇸 `PATH` order wins, empty entries are skipped. 🇧🇷 A ordem do `PATH` vence, entradas vazias são puladas."""
    first, second = _executable(tmp_path / "a"), _executable(tmp_path / "b")
    env = {"PATH": os.pathsep.join(["", str(first.parent), str(second.parent)])}
    assert find("uv", env) == str(first)


def test_find_ignores_relative_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A planted `./uv` never runs. 🇧🇷 Um `./uv` plantado nunca roda."""
    _executable(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert find("uv", {"PATH": os.pathsep.join([".", "bin"])}) is None


@pytest.mark.skipif(os.name == "nt", reason="🇺🇸 no execute bit on Windows · 🇧🇷 sem bit de execução no Windows")
def test_find_skips_files_that_are_not_executable(tmp_path: Path) -> None:
    """🇺🇸 A plain file named `uv` is not a program. 🇧🇷 Um arquivo comum chamado `uv` não é programa."""
    _executable(tmp_path, mode=0o644)
    assert find("uv", {"PATH": str(tmp_path)}) is None


def test_find_without_path_finds_nothing() -> None:
    """🇺🇸 An empty environment. 🇧🇷 Um ambiente vazio."""
    assert find("uv", {}) is None


def test_docker_running_asks_the_engine(programs: Programs) -> None:
    """🇺🇸 A server version means the engine answers. 🇧🇷 Uma versão de servidor significa que o motor responde."""
    programs.answer("docker", "info", stdout="29.0.0\n")
    assert docker_running("/usr/bin/docker")
    programs.answer("docker", "info", stdout="")
    assert not docker_running("/usr/bin/docker")
    programs.answer("docker", "info", returncode=1, stdout="x")
    assert not docker_running("/usr/bin/docker")


@pytest.mark.parametrize("error", [OSError("gone"), subprocess.TimeoutExpired("docker", 20)])
def test_docker_running_survives_a_broken_or_hung_cli(programs: Programs, error: BaseException) -> None:
    """🇺🇸 Not running, not a crash. 🇧🇷 Parado, não uma quebra."""
    programs.fail("docker", "info", error=error)
    assert not docker_running("/usr/bin/docker")


def test_messages_name_the_tool_and_where_to_get_it(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Found on stdout; missing on stderr, with the install page and the way around.

    🇧🇷 Achado no stdout; ausente no stderr.
    """
    found(Output(), "uv", "/usr/bin/uv")
    missing(Output(), "uv", otherwise="pip install x")
    missing(Output(), "docker")
    captured = capsys.readouterr()
    assert "uv found" in captured.out and "/usr/bin/uv" in captured.out
    assert (
        INSTALL_PAGES["uv"] in captured.err
        and "pip install x" in captured.err
        and INSTALL_PAGES["docker"] in captured.err
    )
