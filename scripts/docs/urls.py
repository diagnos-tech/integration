"""🇺🇸 The page ids the site derives from the reference JSON — ported from `urls.ts` to check them before it does.

A generated section expands into one page per route, command or class,
at `<section id>/<slugified segments>`. Two names that slugify alike, or a
name that slugifies outside `PAGE_ID`, would collide or break on the site;
`make docs-check` catches both here, where the name can still be changed.

🇧🇷 Os ids de página que o site deriva do JSON de referência — portados de `urls.ts` para conferi-los antes dele.

Uma seção gerada se expande numa página por rota, comando ou classe, em
`<id da seção>/<segmentos em slug>`. Dois nomes com o mesmo slug, ou um nome
cujo slug sai do `PAGE_ID`, colidiriam ou quebrariam no site; o
`make docs-check` pega os dois aqui, onde o nome ainda pode mudar.
"""

from __future__ import annotations

import re
from typing import Any

from .openapi import HTTP_METHODS


def slugify(value: str) -> str:
    """🇺🇸 `urls.ts`'s `slugify`: `EnrollmentDeniedError` → `enrollment-denied-error`; never empty.

    🇧🇷 O `slugify` de `urls.ts`: `EnrollmentDeniedError` → `enrollment-denied-error`; nunca vazio.
    """
    slug = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "item"


def reference_ids(section: str, kind: str, document: dict[str, Any]) -> list[str]:
    """🇺🇸 Every page id the site generates for one reference section, in document order.

    🇧🇷 Todo id de página que o site gera para uma seção de referência, na ordem do documento.
    """
    if kind == "cli":
        return [
            "/".join([section, *(slugify(part) for part in command["path"])])
            for command in document["commands"]
            if command["path"]
        ]
    if kind == "sdk":
        members = [member for module in document["modules"] for member in module["members"]]
        return [f"{section}/{slugify(member['name'])}" for member in members]
    return [
        f"{section}/{slugify((operation.get('tags') or ['default'])[0])}/{slugify(operation['operationId'])}"
        for item in document["paths"].values()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]
