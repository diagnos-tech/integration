"""🇺🇸 `diagnos/__init__.py`: the SDK's public names load on first use, and only with `diagnos[sdk]`.

🇧🇷 `diagnos/__init__.py`: os nomes públicos do SDK carregam no primeiro uso, e só com `diagnos[sdk]`.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import subprocess
import sys

import pytest

import diagnos
from diagnos import MissingExtraError


def _type_checking_imports() -> dict[str, tuple[str, ...]]:
    """🇺🇸 `{".module": names}` of the `if TYPE_CHECKING:` block.

    🇧🇷 `{".módulo": nomes}` do bloco `if TYPE_CHECKING:`.
    """
    tree = ast.parse(inspect.getsource(diagnos))
    block = next(node for node in tree.body if isinstance(node, ast.If) and ast.unparse(node.test) == "TYPE_CHECKING")
    return {
        "." * node.level + (node.module or ""): tuple(alias.name for alias in node.names)
        for node in block.body
        if isinstance(node, ast.ImportFrom)
    }


def test_the_lazy_map_is_the_type_checking_block() -> None:
    """🇺🇸 What type checkers see is exactly what loads.

    🇧🇷 O que os verificadores de tipo veem é exatamente o que carrega.
    """
    assert _type_checking_imports() == diagnos._SDK


def test_all_is_every_lazy_name_plus_the_base() -> None:
    """🇺🇸 `__all__` hides nothing and invents nothing. 🇧🇷 O `__all__` não esconde nem inventa nada."""
    assert set(diagnos.__all__) == {*diagnos._ORIGIN, "MissingExtraError", "__version__"}
    assert len(diagnos.__all__) == len(set(diagnos.__all__))


@pytest.mark.parametrize("name", sorted(diagnos._ORIGIN))
def test_every_public_name_is_the_object_its_module_defines(name: str) -> None:
    """🇺🇸 `diagnos.X` is `diagnos.<module>.X`, cached after the first access.

    🇧🇷 `diagnos.X` é `diagnos.<módulo>.X`, guardado depois do primeiro acesso.
    """
    module = importlib.import_module(diagnos._ORIGIN[name], "diagnos")
    assert getattr(diagnos, name) is getattr(module, name)
    assert name in vars(diagnos)


@pytest.mark.usefixtures("packages")
def test_without_the_sdk_extra_a_public_name_explains_itself() -> None:
    """🇺🇸 `from diagnos import Diagnos` on the base install: the install command, not a raw `httpx` error.

    🇧🇷 `from diagnos import Diagnos` na instalação base: o comando de instalação, não um erro cru do `httpx`.
    """
    with pytest.raises(MissingExtraError, match=r"diagnos\.Diagnos needs the `sdk` extra"):
        diagnos._load("Diagnos")


def test_an_unknown_name_is_an_attribute_error() -> None:
    """🇺🇸 `hasattr`/`getattr` with a default keep working. 🇧🇷 `hasattr`/`getattr` com padrão continuam funcionando."""
    assert not hasattr(diagnos, "Diagnoss")
    with pytest.raises(AttributeError, match="Diagnoss"):
        diagnos._load("Diagnoss")


def test_dir_lists_names_before_they_load() -> None:
    """🇺🇸 Completion shows the whole surface. 🇧🇷 O autocompletar mostra a superfície inteira."""
    assert {"Diagnos", "Settings", "__version__"} <= set(dir(diagnos))


def test_importing_diagnos_loads_no_dependency() -> None:
    """🇺🇸 A fresh `import diagnos` pulls in neither httpx, pydantic nor the enclave.

    🇧🇷 Um `import diagnos` do zero não puxa httpx, pydantic nem o enclave.
    """
    probe = "import sys, diagnos; print(sorted({'httpx', 'pydantic', 'diagnos._secure'} & set(sys.modules)))"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)  # noqa: S603
    assert result.stdout.strip() == "[]"
