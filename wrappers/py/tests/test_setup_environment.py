"""🇺🇸 Where `diagnos` runs: uv tool, virtual or system, editable, release or not — and the nearest project.

🇧🇷 Onde o `diagnos` roda: uv tool, virtual ou de sistema, editável, release ou não — e o projeto mais próximo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from diagnos._wrapper.setup import environment
from diagnos._wrapper.setup.environment import Environment, project_name, project_root

from conftest import Packages


def _env(**changes: object) -> Environment:
    """🇺🇸 A plain release install in a venv, with `changes`. 🇧🇷 Uma instalação de release num venv, com `changes`."""
    fields: dict[str, object] = {
        "python": "/venv/bin/python",
        "version": "1.2.3",
        "editable": False,
        "uv_tool": False,
        "virtual": True,
    }
    return Environment(**{**fields, **changes})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("version", "release"),
    [
        ("1.2.3", True),
        ("1.2.3rc1", True),
        ("0.0.0+unknown", False),
        ("1.2.3.dev4", False),
        ("1.2", False),
        ("1.2.3\n", False),
    ],
)
def test_only_versions_a_registry_can_hold_are_releases(version: str, release: bool) -> None:
    """🇺🇸 Local and dev segments never reach a command. 🇧🇷 Segmentos locais e de dev nunca chegam a um comando."""
    assert _env(version=version).release is release
    assert _env(version=version).development is not release


def test_editable_is_development_whatever_the_version() -> None:
    """🇺🇸 A checkout stays a checkout. 🇧🇷 Um checkout continua checkout."""
    assert _env(editable=True).development


def test_requirement_pins_this_version() -> None:
    """🇺🇸 Adds the layer, leaves the version alone. 🇧🇷 Soma a camada, deixa a versão."""
    assert _env().requirement("cli") == "diagnos[cli]==1.2.3"


def test_requirement_of_a_development_build_names_no_version() -> None:
    """🇺🇸 `0.0.0+unknown` is never written into a command. 🇧🇷 `0.0.0+unknown` nunca entra num comando."""
    assert _env(version="0.0.0+unknown").requirement("cli") == "diagnos[cli]"


def test_current_reads_this_process(packages: Packages, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """🇺🇸 A uv tool receipt, a venv, a PyPI install. 🇧🇷 Um recibo de uv tool, um venv, uma instalação do PyPI."""
    (tmp_path / "uv-receipt.toml").write_text("")
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert packages.diagnos is not None
    packages.diagnos.direct_url = '{"url": "https://files.pythonhosted.org/x.whl", "archive_info": {}}'
    env = Environment.current()
    assert env.uv_tool and env.virtual and not env.editable
    assert env.python == sys.executable


@pytest.mark.usefixtures("packages")
def test_a_system_python_is_not_virtual(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Outside a venv, with no receipt. 🇧🇷 Fora de um venv, sem recibo."""
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    env = Environment.current()
    assert not env.virtual and not env.uv_tool


@pytest.mark.parametrize(
    ("direct_url", "editable"),
    [
        ('{"dir_info": {"editable": true}}', True),
        ('{"dir_info": {}}', False),
        ("not json", False),
        (None, False),
        ("[]", False),
    ],
)
def test_editable_comes_from_pep_610(packages: Packages, direct_url: str | None, editable: bool) -> None:
    """🇺🇸 Only `dir_info.editable: true` counts. 🇧🇷 Só `dir_info.editable: true` conta."""
    assert packages.diagnos is not None
    packages.diagnos.direct_url = direct_url
    assert environment._editable() is editable


def test_no_metadata_at_all_is_a_source_tree(packages: Packages) -> None:
    """🇺🇸 Never replaced by a release. 🇧🇷 Nunca substituído por um release."""
    packages.diagnos = None
    assert environment._editable()


def test_project_root_is_the_nearest_pyproject(tmp_path: Path) -> None:
    """🇺🇸 Upward from the folder, like `uv`. 🇧🇷 Para cima a partir da pasta, como o `uv`."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "clinic"\n')
    nested = tmp_path / "src" / "app"
    nested.mkdir(parents=True)
    assert project_root(nested) == tmp_path and project_name(tmp_path) == "clinic"


def test_project_root_none_when_there_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 No project anywhere above. 🇧🇷 Nenhum projeto acima."""
    monkeypatch.setattr(Path, "is_file", lambda _self: False)
    assert project_root(tmp_path) is None


@pytest.mark.parametrize("content", ["not toml [", "[project]\nname = 3\n", "[tool.x]\n"])
def test_project_name_is_none_when_unreadable_or_unnamed(tmp_path: Path, content: str) -> None:
    """🇺🇸 Broken, typed wrong, or no `[project]`. 🇧🇷 Quebrado, tipo errado, ou sem `[project]`."""
    (tmp_path / "pyproject.toml").write_text(content)
    assert project_name(tmp_path) is None
    assert project_name(tmp_path / "missing") is None
