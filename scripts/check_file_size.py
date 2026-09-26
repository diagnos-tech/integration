"""🇺🇸 Guard for "small files, one responsibility": no source file above 300 lines, no test file above 500.

The target in `CONTRIBUTING.md` is ~250 lines; the limits here leave room
for a docstring-heavy module without letting one quietly grow into a second
responsibility. A Rust file's inline `#[cfg(test)]` module does not count
against it — those tests belong next to the code they pin. Run:
`uv run python scripts/check_file_size.py` (part of `make lint`).

🇧🇷 Guarda de "arquivos pequenos, uma responsabilidade": nenhum fonte acima de 300 linhas, nenhum teste acima de 500.

A meta no `CONTRIBUTING.md` é ~250 linhas; os limites aqui deixam espaço
para um módulo cheio de docstring sem deixar um crescer, em silêncio, até
virar uma segunda responsabilidade. O módulo `#[cfg(test)]` embutido num
arquivo Rust não conta — esses testes pertencem ao lado do código que
fixam. Rode: `uv run python scripts/check_file_size.py` (parte do `make lint`).
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
    """🇺🇸 Every `.py` and `.rs` file git tracks or would add. 🇧🇷 Todo `.py` e `.rs` rastreado ou a adicionar."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py", "*.rs"],  # noqa: S607 — git on PATH
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return [root / name for name in listed if (root / name).is_file()]


def counted_lines(path: Path) -> int:
    """🇺🇸 Lines that count: all of a Python file; a Rust file up to its `#[cfg(test)]` module.

    🇧🇷 As linhas que contam: todas de um arquivo Python; de um Rust, até o módulo `#[cfg(test)]`.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if path.suffix == ".rs":
        for index, line in enumerate(lines):
            if line.strip() == "#[cfg(test)]":
                return index
    return len(lines)


def limit_for(relative: Path) -> int:
    """🇺🇸 The test limit inside a `tests/` directory, the source limit elsewhere.

    🇧🇷 O limite de teste dentro de um diretório `tests/`, o de fonte no resto.
    """
    return TEST_LIMIT if any(part in _TEST_DIRS for part in relative.parts) else SOURCE_LIMIT


def main() -> int:
    """🇺🇸 Prints every file over its limit; exit code 1 if there is any. 🇧🇷 Lista todo arquivo acima do limite."""
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in _tracked(root):
        relative = path.relative_to(root)
        count, limit = counted_lines(path), limit_for(relative)
        if count > limit:
            offenders.append(f"{relative}: {count} lines (limit {limit})")
    for line in sorted(offenders):
        print(line)
    print(f"{len(offenders)} file(s) over the limit · arquivo(s) acima do limite")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
