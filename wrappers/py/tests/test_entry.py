"""🇺🇸 The console scripts: `diagnos` picks the full CLI or the base, `diagnos-api` checks its extra first.

🇧🇷 Os console scripts: `diagnos` escolhe a CLI completa ou a base, `diagnos-api` confere o extra antes.
"""

from __future__ import annotations

import io
import subprocess
import sys

import pytest

from diagnos import _entry
from diagnos._wrapper.exit_codes import EXIT_UNAVAILABLE

from conftest import Packages


def test_without_the_cli_extra_diagnos_is_the_base(packages: Packages, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 The base answers, and its code is the process's. 🇧🇷 A base responde, e o código dela é o do processo."""
    monkeypatch.setattr(sys, "argv", ["diagnos", "--version"])
    with pytest.raises(SystemExit) as stopped:
        _entry.main()
    assert stopped.value.code == 0


def test_ctrl_c_in_the_base_exits_130(packages: Packages, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 What shells report for an interrupted command. 🇧🇷 O que os shells informam para um comando interrompido."""

    def interrupted(_argv: list[str]) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(_entry, "base", interrupted)
    with pytest.raises(SystemExit) as stopped:
        _entry.main()
    assert stopped.value.code == _entry.EXIT_INTERRUPTED


def test_with_the_cli_extra_diagnos_is_the_full_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 The typer app takes over. 🇧🇷 A app typer assume."""
    called: list[bool] = []
    monkeypatch.setattr("diagnos.cli.main.app", lambda: called.append(True))
    _entry.main()
    assert called == [True]


def test_diagnos_api_without_its_extra_prints_the_fix(packages: Packages, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 No traceback: the install line and `69`. 🇧🇷 Sem traceback: a linha de instalação e `69`."""
    with pytest.raises(SystemExit) as stopped:
        _entry.api()
    assert stopped.value.code == EXIT_UNAVAILABLE
    assert 'pip install "diagnos[api]' in capsys.readouterr().err


def test_diagnos_api_with_its_extra_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Straight to `diagnos.api.main.run`. 🇧🇷 Direto para o `diagnos.api.main.run`."""
    called: list[bool] = []
    monkeypatch.setattr("diagnos.api.main.run", lambda: called.append(True))
    _entry.api()
    assert called == [True]


def test_streams_replace_what_they_cannot_encode(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 An ASCII terminal gets `?`, not a `UnicodeEncodeError`. 🇧🇷 Um terminal ASCII recebe `?`, não um erro."""
    ascii_stdout = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr(sys, "stdout", ascii_stdout)
    monkeypatch.setattr(sys, "stderr", io.StringIO())  # 🇺🇸 not a wrapper: left alone 🇧🇷 não é wrapper: fica como está
    _entry._tolerant_streams()
    print("Não · ✓", end="")
    ascii_stdout.flush()
    assert ascii_stdout.buffer.getvalue() == b"N?o ? ?"


def test_python_m_diagnos_is_the_same_command() -> None:
    """🇺🇸 `python -m diagnos --version`. 🇧🇷 `python -m diagnos --version`."""
    result = subprocess.run([sys.executable, "-m", "diagnos", "--version"], capture_output=True, text=True, check=False)
    assert result.returncode == 0 and result.stdout.startswith("diagnos ")
