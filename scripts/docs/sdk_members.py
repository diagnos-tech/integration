"""What one public class of the SDK exposes: fields, properties and methods, each with its docstring.

The rule for inheritance is the one a reader needs: a member is listed on
the first *public* class that has it. Members of private bases (`_Reading`,
`_OpenedDocument`) belong to their public subclasses — `Drive.download` is
real API even though it is written on `_Reading` — while a public base
(`VaultError`) keeps its own members on its own page, so `ValidationError`
does not repeat them.

Fields have no runtime docstring, so they are read from the source the way
PEP 257 (and pydantic's `use_attribute_docstrings`) define an attribute
docstring: a string literal right after the assignment.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import importlib
import inspect
import typing
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from .l10n import l10n_field
from .sdk_types import signature_text, type_text, value_text


@functools.cache
def attribute_docs(module_name: str) -> dict[str, str]:
    """Returns `{"Class.field" or "NAME": docstring}` for every attribute docstring in one module's source."""
    tree = ast.parse(inspect.getsource(importlib.import_module(module_name)))
    docs: dict[str, str] = {}

    def visit(body: list[ast.stmt], prefix: str) -> None:
        """Pairs each assignment with the string literal right after it."""
        for current, following in zip(body, [*body[1:], None], strict=True):
            if isinstance(current, ast.ClassDef):
                visit(current.body, f"{prefix}{current.name}.")
            targets = current.targets if isinstance(current, ast.Assign) else []
            if isinstance(current, ast.AnnAssign):
                targets = [current.target]
            if (
                isinstance(following, ast.Expr)
                and isinstance(following.value, ast.Constant)
                and isinstance(following.value.value, str)
            ):
                for target in targets:
                    if isinstance(target, ast.Name):
                        docs[f"{prefix}{target.id}"] = inspect.cleandoc(following.value.value)

    visit(tree.body, "")
    return docs


def member(kind: str, name: str, signature: str | None, doc: str | None) -> dict[str, Any]:
    """Returns one `SdkMember` of the contract; `signature` is left out when `None`."""
    entry: dict[str, Any] = {"kind": kind, "name": name, "doc": l10n_field(doc)}
    if signature is not None:
        entry["signature"] = signature
    return entry


def owners(cls: type) -> list[type]:
    """Returns `cls` plus its private SDK bases: the classes whose members its page lists."""
    private = [
        base for base in cls.__mro__[1:] if base.__module__.startswith("diagnos") and base.__name__.startswith("_")
    ]
    return [cls, *private]


def _field_default(cls: type, name: str) -> str | None:
    """Returns the default of a pydantic or dataclass field as source text, `None` when it is required."""
    factory: Callable[[], Any] | None = None
    default: Any = PydanticUndefined
    if issubclass(cls, BaseModel):
        info = cls.model_fields[name]
        default, factory = info.default, info.default_factory  # type: ignore[assignment]
    elif dataclasses.is_dataclass(cls):
        spec = next(item for item in dataclasses.fields(cls) if item.name == name)
        default = PydanticUndefined if spec.default is dataclasses.MISSING else spec.default
        factory = None if spec.default_factory is dataclasses.MISSING else spec.default_factory
    if factory is list:
        return "[]"
    if factory is dict:
        return "{}"
    if factory is not None:
        return "…"
    return None if default is PydanticUndefined else value_text(default)


def _field_type(cls: type, name: str, hints: dict[str, Any]) -> str:
    """Returns the evaluated field type as source text."""
    if issubclass(cls, BaseModel):
        return type_text(cls.model_fields[name].annotation)
    return type_text(hints.get(name, cls.__annotations__.get(name, "")))


def _fields(cls: type, owner: type) -> list[dict[str, Any]]:
    """Returns the fields `owner` declares, in declaration order."""
    try:
        hints = typing.get_type_hints(cls)
    except (NameError, TypeError):
        hints = {}
    docs = attribute_docs(owner.__module__)
    found = []
    for name, annotation in vars(owner).get("__annotations__", {}).items():
        if name.startswith("_") or "ClassVar" in str(annotation):
            continue
        if issubclass(cls, BaseModel) and name not in cls.model_fields:
            continue
        default = _field_default(cls, name)
        signature = f": {_field_type(cls, name, hints)}" + (f" = {default}" if default is not None else "")
        found.append(member("attribute", name, signature, docs.get(f"{owner.__qualname__}.{name}")))
    return found


def _callables(owner: type) -> list[dict[str, Any]]:
    """Returns the public properties and methods `owner` defines, in definition order."""
    found = []
    for name, value in vars(owner).items():
        if name.startswith("_"):
            continue
        if isinstance(value, property) and value.fget is not None:
            returned = inspect.signature(value.fget).return_annotation
            signature = None if returned is inspect.Signature.empty else f": {type_text(returned)}"
            found.append(member("property", name, signature, inspect.getdoc(value)))
        elif isinstance(value, staticmethod):
            found.append(member("method", name, signature_text(value.__func__), inspect.getdoc(value)))
        elif isinstance(value, classmethod) or inspect.isfunction(value):
            function = value.__func__ if isinstance(value, classmethod) else value
            found.append(member("method", name, signature_text(function, drop_first=True), inspect.getdoc(function)))
    return found


def class_members(cls: type) -> list[dict[str, Any]]:
    """Returns every member listed on `cls`'s page: fields first, then properties and methods."""
    fields: list[dict[str, Any]] = []
    callables: list[dict[str, Any]] = []
    for owner in owners(cls):
        fields.extend(_fields(cls, owner))
        callables.extend(_callables(owner))
    seen: set[str] = set()
    unique = []
    for entry in [*fields, *callables]:
        if entry["name"] not in seen:
            seen.add(entry["name"])
            unique.append(entry)
    return unique


def constructor_signature(cls: type) -> str | None:
    """Returns how to build `cls`: pydantic fields as keywords, else `__init__`; `None` when only a builtin makes it."""
    if issubclass(cls, BaseModel):
        parts = []
        for name, info in cls.model_fields.items():
            default = _field_default(cls, name)
            parts.append(f"{name}: {type_text(info.annotation)}" + (f" = {default}" if default is not None else ""))
        return "(*, " + ", ".join(parts) + ")" if parts else "()"
    defines_init = any("__init__" in vars(base) for base in cls.__mro__ if base.__module__.startswith("diagnos"))
    if not (defines_init or dataclasses.is_dataclass(cls)):
        return None
    return signature_text(cls, keep_return=False)


def public_bases(cls: type) -> list[str]:
    """Returns the direct bases by public name.

    A private base is replaced by its own public bases; `object` and `Generic` are dropped.
    """
    names: list[str] = []
    for base in cls.__bases__:
        if base is object or base is typing.Generic:
            continue
        found = public_bases(base) if base.__name__.startswith("_") else [base.__name__.split("[", 1)[0]]
        names.extend(name for name in found if name not in names)
    return names
