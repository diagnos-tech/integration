"""`sdk.json`: the public surface of `diagnos` — exactly `__all__`, in `__all__`'s order — read with `inspect`.

`__all__` is the SDK's own statement of what is public (its package
docstring says anything missing from it is a gap, not an invitation to
reach deeper), so the reference documents that list and nothing else.
Dunder names (`__version__`) are skipped: they are not something a
reference page can usefully explain. A name that is neither a class nor a
function — a type alias such as `TimePrecision` — is an `attribute` whose
signature is its value and whose doc is the attribute docstring written
right under it in the module that defines it.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from typing import Any

from .l10n import l10n_field
from .output import SCHEMA_VERSION, generated_from
from .sdk_members import attribute_docs, class_members, constructor_signature, member, public_bases
from .sdk_types import signature_text, type_text

PACKAGE = "diagnos"


def origins(package: str) -> dict[str, str]:
    """Returns `{name: defining module}` from the package's `from .x import name` lines.

    A type alias carries no `__module__` of its own (`typing` owns it), so
    the import line is the only reliable record of where it was written. The
    SDK's names are imported under `if TYPE_CHECKING:` (they load on first
    use), so the whole tree is walked, not just the top level.
    """
    module = importlib.import_module(package)
    tree = ast.parse(inspect.getsource(module))
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for alias in node.names:
                found[alias.asname or alias.name] = f"{package}.{node.module}"
    return found


def _entry(name: str, obj: object, origin: str) -> dict[str, Any]:
    """Returns one top-level `SdkMember`: a class, an exception, a function or an attribute."""
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
    """Returns the whole `sdk.json` document."""
    module = importlib.import_module(PACKAGE)
    where = origins(PACKAGE)
    names = [name for name in module.__all__ if not (name.startswith("__") and name.endswith("__"))]
    entry: dict[str, Any] = {
        "name": PACKAGE,
        "doc": l10n_field(module.__doc__),
        "members": [_entry(name, getattr(module, name), where.get(name, PACKAGE)) for name in names],
    }
    return {"schemaVersion": SCHEMA_VERSION, "generatedFrom": generated_from(PACKAGE), "modules": [entry]}
