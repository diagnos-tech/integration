"""Guard for the documentation rule: one file per language, always in pairs, never a dead relative link.

Every Markdown document ships as `NAME.md` (English) next to
`NAME.pt-BR.md` (Brazilian Portuguese). This script fails when:

- a document has no sibling in the other language;
- a document does not link to its sibling (the language switcher on top);
- a relative link or image points at a file that does not exist.

Files GitHub renders in a fixed place and that are not documentation (issue and pull request templates, the
changelog) are exempt.

Usage: `uv run python scripts/check_docs.py` (part of `make lint`).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PT_SUFFIX = ".pt-BR.md"
EXEMPT = re.compile(r"^(\.github/(ISSUE_TEMPLATE/|PULL_REQUEST_TEMPLATE)|CHANGELOG\.md$)")
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE = re.compile(r"^(```|~~~)")


def markdown_files(root: Path) -> list[Path]:
    """Lists the Markdown files git tracks or would add, as paths relative to `root`."""
    output = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted({Path(line) for line in output.splitlines() if line and (root / line).exists()})


def sibling(path: Path) -> Path:
    """Returns the path of the same document in the other language."""
    if path.name.endswith(PT_SUFFIX):
        return path.with_name(path.name[: -len(PT_SUFFIX)] + ".md")
    return path.with_name(path.name[: -len(".md")] + PT_SUFFIX)


def links(text: str) -> list[tuple[int, str]]:
    """Returns `(line, target)` for every Markdown link, image or HTML reference outside code fences."""
    found: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        found.extend((number, match.group(1)) for match in LINK.finditer(line))
    for match in re.finditer(r"""(?:src|srcset|href)="([^"]+)\"""", text):
        found.append((text.count("\n", 0, match.start()) + 1, match.group(1)))
    return found


def is_relative(target: str) -> bool:
    """Whether `target` points at a file in this repository (not a URL, not a pure anchor)."""
    return not re.match(r"^([a-z][a-z0-9+.-]*:|#|//)", target, flags=re.IGNORECASE)


def check(root: Path) -> list[str]:
    """Returns every problem found under `root`, each formatted as `file:line: what`."""
    problems: list[str] = []
    for path in markdown_files(root):
        text = (root / path).read_text(encoding="utf-8")
        for number, target in links(text):
            if not is_relative(target):
                continue
            file_part = target.split("#", 1)[0].split("?", 1)[0]
            if file_part and not (root / path.parent / file_part).exists():
                problems.append(f"{path}:{number}: dead link → {target}")
        if EXEMPT.match(path.as_posix()):
            continue
        other = sibling(path)
        if not (root / other).exists():
            problems.append(f"{path}:1: missing translation → {other}")
        elif f"]({other.name})" not in text and f"]({other.name}#" not in text:
            problems.append(f"{path}:1: no language switcher to → {other.name}")
    return problems


def main() -> int:
    """Prints every problem and exits 1 if any document breaks the rule."""
    root = Path(__file__).resolve().parent.parent
    problems = check(root)
    for line in problems:
        print(line)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
