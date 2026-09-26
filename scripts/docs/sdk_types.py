"""🇺🇸 Types and signatures as a reader of the reference wants them: `str | None`, never `typing.Optional[str]`.

Two sources feed the reference and they speak differently. Function
signatures keep the annotation text as written in the source (the SDK uses
`from __future__ import annotations`, so `inspect` hands back those strings
verbatim — `PatientRecord | Mapping[str, Any]`, exactly what a reader of
the code sees). Model fields only exist as evaluated objects, whose `repr`
is noisy and — for pydantic's `Annotated` validators — not even stable
(`<function … at 0x7f…>`). `type_text` renders those objects back into the
source style, deterministically.

🇧🇷 Tipos e assinaturas do jeito que quem lê a referência quer: `str | None`, nunca `typing.Optional[str]`.

Duas fontes alimentam a referência e falam diferente. Assinaturas de função
mantêm o texto da anotação como está no código (o SDK usa `from __future__
import annotations`, então o `inspect` devolve essas strings ao pé da letra —
`PatientRecord | Mapping[str, Any]`, exatamente o que quem lê o código vê).
Campos de modelo só existem como objetos avaliados, cujo `repr` é ruidoso e —
nos validadores `Annotated` do pydantic — nem é estável (`<function … at
0x7f…>`). `type_text` devolve esses objetos ao estilo do código, de forma
determinística.
"""

from __future__ import annotations

import inspect
import re
import types
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar, Union, get_args, get_origin

# 🇺🇸 `diagnos.models.DocumentIndex` → `DocumentIndex`: a dotted lowercase prefix before a name.
# 🇧🇷 `diagnos.models.DocumentIndex` → `DocumentIndex`: um prefixo pontuado minúsculo antes de um nome.
_MODULE_PREFIX = re.compile(r"\b(?:[a-z_][a-z0-9_]*\.)+(?=[A-Za-z_])")


class _Verbatim:
    """🇺🇸 Renders as its text with no quotes — how `inspect.Signature` prints an annotation we already formatted.

    🇧🇷 Renderiza como o próprio texto sem aspas — como o `inspect.Signature` imprime uma anotação já formatada.
    """

    def __init__(self, text: str) -> None:
        """🇺🇸 Holds `text`. 🇧🇷 Guarda `text`."""
        self._text = text

    def __repr__(self) -> str:
        """🇺🇸 The text itself. 🇧🇷 O próprio texto."""
        return self._text


def type_text(annotation: object) -> str:
    """🇺🇸 A type in source style: unions with `|`, no module prefixes, `Annotated` metadata dropped.

    🇧🇷 Um tipo no estilo do código: uniões com `|`, sem prefixo de módulo, metadado de `Annotated` descartado.
    """
    if annotation is None or annotation is type(None):
        return "None"
    if isinstance(annotation, str):
        # 🇺🇸 `builtins.list` is how a class with its own `list` method spells the builtin; readers want `list`.
        # 🇧🇷 `builtins.list` é como uma classe com método `list` próprio escreve o builtin; quem lê quer `list`.
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
    """🇺🇸 A default as source text; an object whose `repr` carries an address becomes `…` (never stable).

    🇧🇷 Um padrão como texto de código; um objeto cujo `repr` carrega endereço vira `…` (nunca é estável).
    """
    text = repr(value)
    return "…" if " at 0x" in text else text


def signature_text(obj: Callable[..., Any], *, drop_first: bool = False, keep_return: bool = True) -> str | None:
    """🇺🇸 `inspect.signature` without the name — `(token=None, *, timeout=30) -> X` — or `None` when there is none.

    `drop_first` removes `self`/`cls` from a method read off its class.

    🇧🇷 `inspect.signature` sem o nome — `(token=None, *, timeout=30) -> X` — ou `None` quando não há.

    `drop_first` tira `self`/`cls` de um método lido da própria classe.
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
