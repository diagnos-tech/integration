"""`make docs`: regenerate `docs/reference/*.json` from the code, at the paths `docs/site.json` declares.

`python -m scripts.docs.generate` writes the three files; `render_all` is
what `make docs-check` compares against the committed ones. The paths come
from the manifest's `reference` map, so the site and this script can never
disagree on where a file lives.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import cli, openapi, sdk, site
from .output import REPO_ROOT, head_commit, read_committed, render, stamp

# `(builder, sort_keys)` per reference kind — see `output.py` for why OpenAPI keeps FastAPI's order.
GENERATORS: dict[str, tuple[Callable[[], dict[str, Any]], bool]] = {
    "openapi": (openapi.build, False),
    "cli": (cli.build, True),
    "sdk": (sdk.build, True),
}


def render_all(root: Path = REPO_ROOT) -> dict[Path, str]:
    """Returns `{path: text}` of every reference file as the code produces it now."""
    references: dict[str, str] = site.load(root)["reference"]
    commit = head_commit(root)
    rendered: dict[Path, str] = {}
    for kind, (build, sort_keys) in GENERATORS.items():
        path = root / references[kind]
        rendered[path] = render(stamp(build(), read_committed(path), commit=commit), sort_keys=sort_keys)
    return rendered


def stale(root: Path = REPO_ROOT) -> list[str]:
    """Returns one problem line per reference file that differs from what `make docs` would write."""
    problems = []
    for path, text in render_all(root).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            where = path.relative_to(root)
            problems.append(f"{where}:1: stale, run `make docs`")
    return problems


def main() -> int:
    """Writes every reference file that changed and reports each one.

    Returns:
        The process exit code, always 0.
    """
    for path, text in render_all().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(REPO_ROOT)}")
        else:
            print(f"unchanged {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
