"""The page ids the site derives from the reference JSON — ported from `urls.ts` to check them before it does.

A generated section expands into one page per route, command or class,
at `<section id>/<slugified segments>`. Two names that slugify alike, or a
name that slugifies outside `PAGE_ID`, would collide or break on the site;
`make docs-check` catches both here, where the name can still be changed.
"""

from __future__ import annotations

import re
from typing import Any

from .openapi import HTTP_METHODS


def slugify(value: str) -> str:
    """Returns `urls.ts`'s `slugify` of `value`: `EnrollmentDeniedError` → `enrollment-denied-error`; never empty."""
    slug = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "item"


def reference_ids(section: str, kind: str, document: dict[str, Any]) -> list[str]:
    """Returns every page id the site generates for one reference section, in document order.

    Args:
        section: The id of the manifest's reference page, the prefix of every generated id.
        kind: The reference kind: `cli`, `sdk` or `openapi`.
        document: The parsed reference JSON of that kind.
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
