"""🇺🇸 `diagnos._extras`: which layers are installed, read from metadata — and the real metadata stays readable.

🇧🇷 `diagnos._extras`: quais camadas estão instaladas, lidas dos metadados — e os metadados reais continuam legíveis.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from diagnos import _extras
from diagnos._extras import MissingExtraError, extras, install_hint, installed, require

from conftest import FakeDistribution, Packages

ROOT = Path(__file__).resolve().parents[3]
# 🇺🇸 Every distribution an extra may pull in; a new one is a reviewed change to this list.
# 🇧🇷 Toda distribuição que um extra pode puxar; uma nova é uma mudança revisada nesta lista.
ALLOWED = {
    "diagnos",
    "httpx",
    "pydantic",
    "hvac",
    "typer",
    "rich",
    "fastapi",
    "uvicorn",
    "python-multipart",
    "cryptography",
}


def test_nothing_is_installed_on_the_base(packages: Packages) -> None:
    """🇺🇸 A bare `pip install diagnos`: every extra missing. 🇧🇷 Um `pip install diagnos` puro: todo extra ausente."""
    assert [installed(extra) for extra in extras()] == [False] * 5


def test_an_extra_needs_its_own_and_its_layers_dependencies(packages: Packages) -> None:
    """🇺🇸 `cli` counts only with the SDK's dependencies too. 🇧🇷 O `cli` só conta com as dependências do SDK também."""
    packages.present = {"typer", "rich"}
    assert not installed("cli")
    packages.present |= {"httpx", "pydantic"}
    assert installed("cli") and installed("sdk")
    assert not installed("api")


def test_names_match_whatever_their_spelling(packages: Packages) -> None:
    """🇺🇸 `Python_Multipart` is `python-multipart` (PEP 503). 🇧🇷 `Python_Multipart` é `python-multipart` (PEP 503)."""
    assert packages.diagnos is not None
    packages.diagnos.requires = ['Diagnos[sdk]; extra == "api"', 'Python_Multipart>=0.0.12 ; extra == "api"']
    packages.present = {"Python_Multipart"}
    assert installed("api")


def test_lines_without_a_plain_extra_marker_are_ignored(packages: Packages) -> None:
    """🇺🇸 Base requirements and other markers never block a layer.

    🇧🇷 Requisitos da base e outros marcadores não bloqueiam.
    """
    assert packages.diagnos is not None
    packages.diagnos.requires = ["typing-extensions>=4", 'uvloop; sys_platform != "win32" and extra == "api"', "!!"]
    assert installed("api")


def test_a_source_tree_nobody_installed_answers_yes(packages: Packages) -> None:
    """🇺🇸 No metadata: let the import speak instead. 🇧🇷 Sem metadados: deixar o import falar no lugar."""
    packages.diagnos = None
    assert installed("cli") and extras() == ()


def test_an_unknown_extra_is_a_programming_error(packages: Packages) -> None:
    """🇺🇸 A typo must not read as "not installed". 🇧🇷 Um erro de digitação não pode parecer "não instalado"."""
    with pytest.raises(ValueError, match="cli-typo"):
        installed("cli-typo")


def test_guided_extras_come_first(packages: Packages) -> None:
    """🇺🇸 `sdk`, `cli`, `api`, then the rest alphabetically. 🇧🇷 `sdk`, `cli`, `api`, depois o resto em ordem."""
    assert extras() == ("sdk", "cli", "api", "dev-certs", "openbao")


def test_require_names_the_command_that_adds_the_layer(packages: Packages, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 The error is the fix, at this very version. 🇧🇷 O erro é a correção, nesta mesma versão."""
    monkeypatch.setattr(_extras, "__version__", "1.2.3")
    with pytest.raises(
        MissingExtraError, match=re.escape('pip install "diagnos[cli]==1.2.3" (or · ou: diagnos setup cli)')
    ) as error:
        require("cli", "diagnos.cli")
    assert isinstance(error.value, ImportError) and error.value.extra == "cli"
    packages.present = {"httpx", "pydantic"}
    require("sdk", "diagnos.Diagnos")


def test_only_guided_extras_mention_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `diagnos setup openbao` does not exist. 🇧🇷 O `diagnos setup openbao` não existe."""
    monkeypatch.setattr(_extras, "__version__", "1.2.3")
    assert install_hint("openbao") == 'pip install "diagnos[openbao]==1.2.3"'


def test_a_development_build_names_no_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `0.0.0+unknown` is not on PyPI. 🇧🇷 `0.0.0+unknown` não está no PyPI."""
    monkeypatch.setattr(_extras, "__version__", "0.0.0+unknown")
    assert install_hint("cli") == 'pip install "diagnos[cli]" (or · ou: diagnos setup cli)'


def test_the_real_metadata_keeps_markers_the_parser_reads() -> None:
    """🇺🇸 Every `Requires-Dist` of the installed `diagnos` is a plain `extra == "…"`, onto allowed distributions.

    🇧🇷 Todo `Requires-Dist` do `diagnos` instalado é um `extra == "…"` simples, sobre distribuições permitidas.
    """
    _extras._declared.cache_clear()
    declared = _extras._declared()
    assert declared is not None and set(declared) == {"sdk", "openbao", "cli", "api", "dev-certs"}
    names = {_extras._normalized(name) for requirements in declared.values() for name, _ in requirements}
    assert names <= ALLOWED
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    assert project["dependencies"] == []
    assert sum(len(requirements) for requirements in project["optional-dependencies"].values()) == sum(
        len(requirements) for requirements in declared.values()
    )


def test_fake_distribution_reads_only_direct_url() -> None:
    """🇺🇸 The fake answers nothing else. 🇧🇷 O falso não responde mais nada."""
    assert FakeDistribution(direct_url="{}").read_text("METADATA") is None
