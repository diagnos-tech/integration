"""🇺🇸 `diagnos setup sdk` and `diagnos setup cli`: where each layer goes, and when nothing should run.

🇧🇷 `diagnos setup sdk` e `diagnos setup cli`: para onde cada camada vai, e quando nada deve rodar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from diagnos._wrapper.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_UNAVAILABLE
from diagnos._wrapper.output import Output
from diagnos._wrapper.setup import python, setup
from diagnos._wrapper.setup.environment import Environment
from diagnos._wrapper.setup.run import Plan

from conftest import Packages

UV = "/opt/bin/uv"


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """🇺🇸 The environment `setup` sees, editable per test; `uv` is on `PATH`.

    🇧🇷 O ambiente que o `setup` vê; o `uv` existe.
    """
    fields: dict[str, object] = {
        "python": "/venv/bin/python",
        "version": "1.2.3",
        "editable": False,
        "uv_tool": False,
        "externally_managed": False,
        "virtual": True,
    }
    monkeypatch.setattr(Environment, "current", classmethod(lambda _cls: Environment(**fields)))  # type: ignore[arg-type]
    monkeypatch.setattr(python, "find", lambda name: UV if name == "uv" else None)
    return fields


def _argv(plan: Plan | int) -> list[str]:
    """🇺🇸 The commands a plan shows. 🇧🇷 Os comandos que um plano mostra."""
    assert isinstance(plan, Plan)
    return [step.shown for step in plan.steps]


@pytest.mark.usefixtures("packages")
def test_sdk_goes_into_the_project_with_uv_add(env: dict[str, object], tmp_path: Path) -> None:
    """🇺🇸 `uv add` with a floor at this version. 🇧🇷 `uv add` com piso nesta versão."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "clinic"\n')
    assert _argv(python.sdk(Output(), cwd=tmp_path)) == [f"uv add --project {tmp_path} 'diagnos[sdk]>=1.2.3'"]


@pytest.mark.usefixtures("packages")
def test_sdk_outside_a_project_goes_into_the_venv(env: dict[str, object], tmp_path: Path) -> None:
    """🇺🇸 The venv that runs `diagnos`, pinned. 🇧🇷 O venv que roda o `diagnos`, fixado."""
    assert _argv(python.sdk(Output(), cwd=tmp_path)) == [
        "uv pip install --python /venv/bin/python 'diagnos[sdk]==1.2.3'"
    ]


def test_sdk_already_in_the_venv_is_done(env: dict[str, object], packages: Packages, tmp_path: Path) -> None:
    """🇺🇸 Nothing to run. 🇧🇷 Nada a rodar."""
    packages.present = {"httpx", "pydantic"}
    assert python.sdk(Output(), cwd=tmp_path) == EXIT_OK


@pytest.mark.usefixtures("packages")
@pytest.mark.parametrize("change", [{"uv_tool": True}, {"virtual": False}])
def test_sdk_from_a_tool_or_system_python_creates_a_project(
    env: dict[str, object], tmp_path: Path, change: dict[str, object]
) -> None:
    """🇺🇸 `uv init --bare` here, then `uv add`. 🇧🇷 `uv init --bare` aqui, depois `uv add`."""
    env.update(change)
    assert _argv(python.sdk(Output(), cwd=tmp_path)) == [
        f"uv init --bare --no-workspace {tmp_path}",
        f"uv add --project {tmp_path} 'diagnos[sdk]>=1.2.3'",
    ]


@pytest.mark.usefixtures("packages")
def test_sdk_of_a_dev_version_adds_without_a_floor(env: dict[str, object], tmp_path: Path) -> None:
    """🇺🇸 `>=0.0.0+unknown` is not a valid specifier. 🇧🇷 `>=0.0.0+unknown` não é um especificador válido."""
    env["version"] = "0.0.0+unknown"
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "clinic"\n')
    assert _argv(python.sdk(Output(), cwd=tmp_path)) == [f"uv add --project {tmp_path} 'diagnos[sdk]'"]


@pytest.mark.usefixtures("packages")
def test_sdk_inside_this_repository_is_development(
    env: dict[str, object], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Never `uv add diagnos` to `diagnos` itself. 🇧🇷 Nunca `uv add diagnos` no próprio `diagnos`."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "diagnos"\n')
    assert python.sdk(Output(), cwd=tmp_path) == EXIT_FAILED
    assert "uv sync" in capsys.readouterr().err


@pytest.mark.usefixtures("packages")
def test_without_uv_the_sdk_says_how_to_go_on(
    env: dict[str, object], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 The install page, and the pip line that works without uv.

    🇧🇷 A página de instalação, e a linha do pip sem uv.
    """
    monkeypatch.setattr(python, "find", lambda _name: None)
    assert python.sdk(Output(), cwd=tmp_path) == EXIT_UNAVAILABLE
    assert 'python -m pip install "diagnos[sdk]==1.2.3"' in capsys.readouterr().err


@pytest.mark.usefixtures("packages")
def test_cli_goes_into_the_environment_that_runs_diagnos(env: dict[str, object]) -> None:
    """🇺🇸 The same `diagnos` gains every command. 🇧🇷 O mesmo `diagnos` ganha todo comando."""
    assert _argv(python.cli(Output())) == ["uv pip install --python /venv/bin/python 'diagnos[cli]==1.2.3'"]


@pytest.mark.usefixtures("packages")
@pytest.mark.parametrize("change", [{"uv_tool": True}, {"externally_managed": True}])
def test_cli_from_a_tool_or_managed_python_is_a_uv_tool(env: dict[str, object], change: dict[str, object]) -> None:
    """🇺🇸 The receipt keeps the extra; the system Python is never written.

    🇧🇷 O recibo guarda o extra; o Python do sistema não é escrito.
    """
    env.update(change)
    assert _argv(python.cli(Output())) == ["uv tool install 'diagnos[cli]==1.2.3'"]


def test_cli_already_installed_is_done(
    env: dict[str, object], packages: Packages, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Points at the commands instead. 🇧🇷 Aponta para os comandos no lugar."""
    packages.present = {"httpx", "pydantic", "typer", "rich"}
    assert python.cli(Output()) == EXIT_OK
    assert "diagnos --help" in capsys.readouterr().out


@pytest.mark.usefixtures("packages")
def test_cli_in_a_checkout_is_development(env: dict[str, object]) -> None:
    """🇺🇸 A PyPI wheel must not replace an editable install.

    🇧🇷 Um wheel do PyPI não pode substituir uma instalação editável.
    """
    env["editable"] = True
    assert python.cli(Output()) == EXIT_FAILED


@pytest.mark.usefixtures("packages")
def test_without_uv_the_cli_is_unavailable(env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Exit `69`. 🇧🇷 Saída `69`."""
    monkeypatch.setattr(python, "find", lambda _name: None)
    assert python.cli(Output()) == EXIT_UNAVAILABLE


@pytest.mark.usefixtures("packages")
def test_setup_dispatches_by_target(env: dict[str, object], tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 A plan is carried out; an early answer is returned as is.

    🇧🇷 Um plano é executado; uma resposta antecipada volta como está.
    """
    assert setup("sdk", assume_yes=False, dry_run=True, out=Output(), cwd=tmp_path) == EXIT_OK
    assert "uv pip install" in capsys.readouterr().out
    env["editable"] = True
    assert setup("cli", assume_yes=False, dry_run=True, out=Output()) == EXIT_FAILED
