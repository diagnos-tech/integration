"""Types and signatures as a reader of the reference wants them: `str | None`, never `typing.Optional[str]`.

Two sources feed the reference and they speak differently. Function
signatures keep the annotation text as written in the source (the SDK uses
`from __future__ import annotations`, so `inspect` hands back those strings
verbatim — `PatientRecord | Mapping[str, Any]`, exactly what a reader of
the code sees). Model fields only exist as evaluated objects, whose `repr`
is noisy and — for pydantic's `Annotated` validators — not even stable
(`<function … at 0x7f…>`). `type_text` renders those objects back into the
source style, deterministically.
"""

from __future__ import annotations

import inspect
import re
import types
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar, Union, get_args, get_origin

# `diagnos.models.DocumentIndex` → `DocumentIndex`: a dotted lowercase prefix before a name.
_MODULE_PREFIX = re.compile(r"\b(?:[a-z_][a-z0-9_]*\.)+(?=[A-Za-z_])")


class _Verbatim:
    """Renders as its text with no quotes, which is how `inspect.Signature` prints an annotation already formatted."""

    def __init__(self, text: str) -> None:
        """Holds `text`."""
        self._text = text

    def __repr__(self) -> str:
        """Returns the text itself."""
        return self._text


def type_text(annotation: object) -> str:
    """Returns a type in source style: unions with `|`, no module prefixes, `Annotated` metadata dropped."""
    if annotation is None or annotation is type(None):
        return "None"
    if isinstance(annotation, str):
        # `builtins.list` is how a class with its own `list` method spells the builtin; readers want `list`.
        return annotation.replace("builtins.", "")
    if isinstance(annotation, list):
        return "[" + ", ".join(type_text(item) for item in annotation) + "]"
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Annotated:
        return type_text(args[0])
    if origin is Union or origin is types.UnionType:
        return " | ".join(type_text(arg) for arg in args)
    if origin is Literal:
        return "Literal[" + ", ".join(repr(arg) for arg in args) + "]"
    if origin is not None and args:
        return f"{getattr(origin, '__name__', repr(origin))}[{', '.join(type_text(arg) for arg in args)}]"
    if isinstance(annotation, TypeVar):
        return annotation.__name__
    if isinstance(annotation, type):
        return annotation.__qualname__
    return _MODULE_PREFIX.sub("", repr(annotation))


def value_text(value: object) -> str:
    """Returns a default as source text; an object whose `repr` carries an address becomes `…` (never stable)."""
    text = repr(value)
    return "…" if " at 0x" in text else text


def signature_text(obj: Callable[..., Any], *, drop_first: bool = False, keep_return: bool = True) -> str | None:
    """Returns `inspect.signature` without the name, as in `(token=None, *, timeout=30) -> X`.

    Args:
        obj: The class or callable to describe.
        drop_first: Drops the first parameter (`self` or `cls`) of a method read off its class.
        keep_return: Keeps the return annotation; a class signature has none worth showing.

    Returns:
        The signature text, or `None` when `inspect` cannot produce one.
    """
    try:
        signature = inspect.signature(obj)
    except (TypeError, ValueError):
        return None
    parameters = list(signature.parameters.values())[1 if drop_first else 0 :]
    rendered = [
        parameter.replace(
            annotation=(
                parameter.empty
                if parameter.annotation is parameter.empty
                else _Verbatim(type_text(parameter.annotation))
            ),
            default=parameter.empty
            if parameter.default is parameter.empty
            else _Verbatim(value_text(parameter.default)),
        )
        for parameter in parameters
    ]
    returned = signature.return_annotation
    return_text = (
        _Verbatim(type_text(returned)) if keep_return and returned is not signature.empty else inspect.Signature.empty
    )
    return str(signature.replace(parameters=rendered, return_annotation=return_text))
