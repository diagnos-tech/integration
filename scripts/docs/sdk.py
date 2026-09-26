"""🇺🇸 `sdk.json`: the public surface of `diagnos` — exactly `__all__`, in `__all__`'s order — read with `inspect`.

`__all__` is the SDK's own statement of what is public (its package
docstring says anything missing from it is a gap, not an invitation to
reach deeper), so the reference documents that list and nothing else.
Dunder names (`__version__`) are skipped: they are not something a
reference page can usefully explain. A name that is neither a class nor a
function — a type alias such as `TimePrecision` — is an `attribute` whose
signature is its value and whose doc is the attribute docstring written
right under it in the module that defines it.

🇧🇷 `sdk.json`: a superfície pública do `diagnos` — exatamente o `__all__`, na ordem do `__all__` — lida com `inspect`.

O `__all__` é a declaração do próprio SDK do que é público (a docstring do
pacote diz que o que falta nele é lacuna, não convite para ir mais fundo),
então a referência documenta essa lista e nada mais. Nomes dunder
(`__version__`) ficam de fora: não são algo que uma página de referência
explique com proveito. Um nome que não é classe nem função — um alias de
tipo como `TimePrecision` — é um `attribute` cuja assinatura é o próprio
valor e cuja doc é a docstring de atributo escrita logo abaixo dele no
módulo que o define.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from typing import Any

from .bilingual import l10n_field
from .output import SCHEMA_VERSION, generated_from
from .sdk_members import attribute_docs, class_members, constructor_signature, member, public_bases
from .sdk_types import signature_text, type_text

PACKAGE = "diagnos"


def origins(package: str) -> dict[str, str]:
    """🇺🇸 `{name: defining module}` from the package's `from .x import name` lines.

    A type alias carries no `__module__` of its own (`typing` owns it), so
    the import line is the only reliable record of where it was written.

    🇧🇷 `{nome: módulo que o define}` a partir das linhas `from .x import nome` do pacote.

    Um alias de tipo não carrega `__module__` próprio (é do `typing`), então a
    linha de import é o único registro confiável de onde ele foi escrito.
    """
    module = importlib.import_module(package)
    tree = ast.parse(inspect.getsource(module))
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for alias in node.names:
                found[alias.asname or alias.name] = f"{package}.{node.module}"
    return found


def _entry(name: str, obj: object, origin: str) -> dict[str, Any]:
    """🇺🇸 One top-level `SdkMember`: a class, an exception, a function or an attribute.

    🇧🇷 Um `SdkMember` de topo: uma classe, uma exceção, uma função ou um atributo.
    """
    alias_doc = attribute_docs(origin).get(name)
    if inspect.isclass(obj):
        kind = "exception" if issubclass(obj, BaseException) else "class"
        entry = member(kind, name, constructor_signature(obj), alias_doc or inspect.getdoc(obj))
        entry["bases"] = public_bases(obj)
        entry["members"] = class_members(obj)
        return entry
    if inspect.isfunction(obj):
        return member("function", name, signature_text(obj), inspect.getdoc(obj))
    return member("attribute", name, f" = {type_text(obj)}", alias_doc)


def build() -> dict[str, Any]:
    """🇺🇸 The whole `sdk.json` document. 🇧🇷 O documento `sdk.json` inteiro."""
    module = importlib.import_module(PACKAGE)
    where = origins(PACKAGE)
    names = [name for name in module.__all__ if not (name.startswith("__") and name.endswith("__"))]
    doc, untranslated = l10n_field(module.__doc__)
    entry: dict[str, Any] = {
        "name": PACKAGE,
        "doc": doc,
        "members": [_entry(name, getattr(module, name), where.get(name, PACKAGE)) for name in names],
    }
    if untranslated:
        entry["untranslated"] = True
    return {"schemaVersion": SCHEMA_VERSION, "generatedFrom": generated_from(PACKAGE), "modules": [entry]}


def untranslated(document: dict[str, Any]) -> list[str]:
    """🇺🇸 Dotted names of every entry flagged `untranslated`. 🇧🇷 Nomes pontuados de toda entrada `untranslated`."""
    found: list[str] = []

    def visit(entries: list[dict[str, Any]], prefix: str) -> None:
        """🇺🇸 Walks members recursively. 🇧🇷 Percorre membros recursivamente."""
        for item in entries:
            if item.get("untranslated"):
                found.append(f"{prefix}{item['name']}")
            visit(item.get("members", []), f"{prefix}{item['name']}.")

    visit(document.get("modules", []), "")
    return found
