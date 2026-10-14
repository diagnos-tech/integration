"""Guard for "small files, one responsibility": no source file above 300 lines, no test file above 500.

The target in `CONTRIBUTING.md` is about 250 lines; the limits here leave room for a docstring-heavy module
without letting one quietly grow into a second responsibility. A Rust file's inline `#[cfg(test)]` module does not
count against it: those tests belong next to the code they pin.

Usage: `uv run python scripts/check_file_size.py` (part of `make lint`).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

SOURCE_LIMIT: Final = 300
TEST_LIMIT: Final = 500
_TEST_DIRS: Final = ("tests",)


def _tracked(root: Path) -> list[Path]:
    """Lists every `.py` and `.rs` file git tracks or would add."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py", "*.rs"],  # noqa: S607 — git on PATH
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return [root / name for name in listed if (root / name).is_file()]


def counted_lines(path: Path) -> int:
    """Counts the lines that matter: all of a Python file, or a Rust file up to its `#[cfg(test)]` module."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if path.suffix == ".rs":
        for index, line in enumerate(lines):
            if line.strip() == "#[cfg(test)]":
                return index
    return len(lines)


def limit_for(relative: Path) -> int:
    """Returns the test limit inside a `tests/` directory and the source limit elsewhere."""
    return TEST_LIMIT if any(part in _TEST_DIRS for part in relative.parts) else SOURCE_LIMIT


def main() -> int:
    """Prints every file over its limit and exits 1 if there is any."""
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in _tracked(root):
        relative = path.relative_to(root)
        count, limit = counted_lines(path), limit_for(relative)
        if count > limit:
            offenders.append(f"{relative}: {count} lines (limit {limit})")
    for line in sorted(offenders):
        print(line)
    print(f"{len(offenders)} file(s) over the limit")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
