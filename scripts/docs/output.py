"""How a generated JSON is written: deterministic text, and a `generatedFrom` that never churns on its own.

Determinism is what makes `make docs-check` possible at all: regenerating
must produce byte-identical files when the code did not change, so the
freshness check can be a plain text comparison. Two rules get there:

- the text is always `json.dumps(indent=2, ensure_ascii=False)` plus one
  trailing newline; `sort_keys` for the documents this repo shapes
  (`cli.json`, `sdk.json`), declaration order for `openapi.json` — sorting
  would scramble the field order of every schema the site shows;
- `generatedFrom.commit` is the commit the reference was *last regenerated
  on top of*: it is carried over from the committed file while nothing else
  changed, and only restamped with `HEAD` when the content really moved.
  Stamping `HEAD` blindly would make every commit stale the next one.
"""

from __future__ import annotations

import json
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1


def render(document: object, *, sort_keys: bool) -> str:
    """Returns the exact text a generated file holds: indented JSON and one trailing newline."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n"


def head_commit(root: Path = REPO_ROOT) -> str:
    """Returns the short SHA of `HEAD`, or `unknown` outside a git checkout (a source tarball)."""
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def generated_from(package: str) -> dict[str, str]:
    """Returns the contract's `GeneratedFrom`, with the commit left for `stamp` to decide."""
    return {"package": package, "version": version(package), "commit": ""}


def stamp(fresh: dict[str, Any], committed: dict[str, Any] | None, *, commit: str) -> dict[str, Any]:
    """Returns `fresh` with `generatedFrom.commit` set.

    The commit is the committed file's own when nothing else changed, and `commit` otherwise.

    Args:
        fresh: The document as the code produces it now.
        committed: The document currently on disk, or `None` when there is none.
        commit: The short SHA to stamp when the content changed.

    Returns:
        The stamped document, or `fresh` itself when it has no `generatedFrom` envelope (OpenAPI).
    """
    if "generatedFrom" not in fresh:
        return fresh
    previous = committed.get("generatedFrom", {}).get("commit") if committed else None
    carried = {**fresh, "generatedFrom": {**fresh["generatedFrom"], "commit": previous}}
    if previous and committed is not None and carried == committed:
        return carried
    return {**fresh, "generatedFrom": {**fresh["generatedFrom"], "commit": commit}}


def read_committed(path: Path) -> dict[str, Any] | None:
    """Returns the JSON object currently on disk, or `None` when the file is missing, unparsable or not an object."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None
