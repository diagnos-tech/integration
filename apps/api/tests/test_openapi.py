"""`/openapi.json` matches the prefix table of `README.md`, and its operations are documented in English only.

Every route, parameter and schema is in the generated reference (`docs/reference/openapi.json`, kept fresh by
`make docs-check`). What stays hand-written is the short table of prefixes in `README.md`, which a human skims first,
so nothing stops it from drifting out of sync with the routers as they grow. This file parses that table and checks it
both ways: every prefix it lists still has a real route under it, and every route FastAPI serves falls under a listed
prefix. Separately, every operation that FastAPI generated carries an English `summary` and `description`, the one
artifact an external caller reads instead of the source.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

_README = Path(__file__).parent.parent / "README.md"

# A README row looks like `| `/v1/drives/{sg}` | files and folders … |`. Only the first backtick-quoted cell (the
# prefix) matters here; "What it serves" is prose, not part of the route contract.
_ROW = re.compile(r"^\| `(/[^`]*)` \|", re.MULTILINE)

_METHODS = ("get", "post", "put", "delete", "patch")

# The US and Brazil flag emoji (as escapes) and " · " once marked a translation; Portuguese letters catch the rest.
_NOT_ENGLISH = re.compile(r"\U0001F1FA\U0001F1F8|\U0001F1E7\U0001F1F7| · |[ãõçáéíóúâêôà]", re.IGNORECASE)


def _normalize(path: str) -> str:
    """Collapses any `{param}` segment to `{}` so `{sg}` (README) matches whatever the real route names it."""
    return re.sub(r"\{[^}]+\}", "{}", path)


def _readme_prefixes() -> list[str]:
    """Every prefix in `README.md`'s table, normalized, in file order."""
    return [_normalize(prefix) for prefix in _ROW.findall(_README.read_text(encoding="utf-8"))]


def _served_paths(client: TestClient) -> set[str]:
    """Every path FastAPI serves an operation on, normalized."""
    spec = client.get("/openapi.json").json()
    return {_normalize(path) for path, item in spec["paths"].items() if any(method in item for method in _METHODS)}


def _is_under(path: str, prefix: str) -> bool:
    """`path` is `prefix` itself or a route below it."""
    return path == prefix or path.startswith(prefix + "/")


def test_readme_lists_the_documented_prefixes(client: TestClient) -> None:
    """Sanity check on the parser itself: the table has to have found real rows, not zero from a bad regex."""
    assert len(_readme_prefixes()) >= 5


def test_every_readme_prefix_has_a_route_and_every_route_a_readme_prefix(client: TestClient) -> None:
    """The README's table and the routers agree both ways: no prefix without a route, no route without a prefix.

    A prefix with nothing under it means the README documents routes that no longer exist. A served path under no prefix
    means a router was added without a row in the table that an integrator reads first. Either way, this is exactly the
    kind of drift a test should catch instead of a human noticing months later.
    """
    prefixes, served = _readme_prefixes(), _served_paths(client)

    for prefix in prefixes:
        assert any(_is_under(path, prefix) for path in served), f"{prefix} is documented but nothing is served under it"
    for path in sorted(served):
        assert any(_is_under(path, prefix) for prefix in prefixes), f"{path} is served but under no documented prefix"


def _texts(node: object) -> list[str]:
    """Collects every `summary` and `description` string under `node`, however deeply nested."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("summary", "description") and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_texts(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_texts(item))
    return found


def test_every_operation_is_documented_in_english_only(client: TestClient) -> None:
    """Every operation has a `summary` and a `description`, and no OpenAPI text is bilingual.

    The text under `paths` (operations, parameters, responses), `info` and `tags` comes from this package and is what
    an integrator reads in `/docs`, so it must carry no translation marker and no Portuguese letters.
    """
    spec = client.get("/openapi.json").json()
    checked = 0
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in _METHODS:
                continue
            assert operation.get("summary"), f"{method.upper()} {path} has no summary"
            assert operation.get("description"), f"{method.upper()} {path} has no description"
            checked += 1

    for text in _texts(spec["paths"]) + _texts(spec["info"]) + _texts(spec["tags"]):
        assert not _NOT_ENGLISH.search(text), f"not English-only: {text!r}"

    # Guards the loop itself: an empty `spec["paths"]` would make every assertion above vacuously true.
    assert checked >= 20
