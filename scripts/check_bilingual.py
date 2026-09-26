"""🇺🇸 Guard for the bilingual docstring rule in `CONVENTIONS.md`.

Every module, class and public function must carry a docstring with both the
🇺🇸 and the 🇧🇷 paragraphs. Ruff enforces that docstrings exist; this script
enforces that they speak both languages. The same rule applies to `native/`'s
Rust doc comments (`//!` module docs, `///` item docs) — `rustdoc`/clippy have
no equivalent of this check, so it lives here too.
Run: `uv run python scripts/check_bilingual.py apps/sdk apps/cli apps/api contracts scripts`.

🇧🇷 Guarda da regra de docstring bilíngue de `CONVENTIONS.md`.

Todo módulo, classe e função pública precisa de docstring com os dois
parágrafos, 🇺🇸 e 🇧🇷. O ruff garante que docstrings existem; este script
garante que falam as duas línguas. A mesma regra vale para os comentários de
doc em Rust do `native/` (`//!` de módulo, `///` de item) — `rustdoc`/clippy
não têm equivalente desta checagem, então ela mora aqui também.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FLAGS = ("🇺🇸", "🇧🇷")
RUST_DOC_MARKERS = ("//!", "///")


def _missing_flags(text: str) -> str | None:
    """🇺🇸 First of `FLAGS` missing from `text`, or `None`. 🇧🇷 Primeira de `FLAGS` ausente em `text`, ou `None`."""
    for flag in FLAGS:
        if flag not in text:
            return flag
    return None


def _missing(node: ast.AST) -> str | None:
    """🇺🇸 The flag a docstring lacks, or `None`. 🇧🇷 A bandeira que falta na docstring, ou `None`."""
    doc = ast.get_docstring(node)  # type: ignore[arg-type]
    if doc is None:
        return "docstring"
    return _missing_flags(doc)


def _rust_doc_blocks(text: str, marker: str) -> list[tuple[int, str]]:
    """🇺🇸 Runs of `marker` in `text`, with each start line. 🇧🇷 Trechos de `marker` em `text`, com a linha de cada um."""
    # 🇺🇸 No AST here: `rustdoc` itself groups a doc block this way — same
    #    marker, nothing else between — so a comment check needs no more.
    # 🇧🇷 Sem AST aqui: o próprio `rustdoc` agrupa um bloco de doc assim —
    #    mesmo marcador, nada entre — então uma checagem de comentário não
    #    precisa de mais que isso.
    blocks: list[tuple[int, str]] = []
    start = 0
    chunk: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith(marker):
            if not chunk:
                start = lineno
            chunk.append(line)
        elif chunk:
            blocks.append((start, "\n".join(chunk)))
            chunk = []
    if chunk:
        blocks.append((start, "\n".join(chunk)))
    return blocks


def check_rust(path: Path) -> list[str]:
    """🇺🇸 Problems in one `.rs` file, as `file:line: what`. 🇧🇷 Problemas de um `.rs`, como `arquivo:linha: o quê`."""
    text = path.read_text(encoding="utf-8")
    findings: list[tuple[int, str]] = []
    for marker in RUST_DOC_MARKERS:
        for lineno, block in _rust_doc_blocks(text, marker):
            if (why := _missing_flags(block)) is not None:
                findings.append((lineno, why))
    return [f"{path}:{lineno}: doc missing {why}" for lineno, why in sorted(findings)]


def check(path: Path, *, top_level_only: bool = False) -> list[str]:
    """🇺🇸 Problems in one file, as `file:line: what`; `top_level_only` for tests: module, classes, functions.

    In a test file the module, each test, fixture, helper and fake class is
    what a reader needs explained; a fake's methods mirror the SDK methods
    documented where they are defined, and a closure lives three lines from
    its use.

    🇧🇷 Problemas de um arquivo, como `arquivo:linha: o quê`; `top_level_only` para testes: módulo, classes, funções.

    Num arquivo de teste, o módulo, cada teste, fixture, ajudante e classe
    falsa é o que quem lê precisa ver explicado; os métodos de um fake
    espelham os métodos do SDK documentados onde são definidos, e uma closure
    vive a três linhas do uso.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if (why := _missing(tree)) is not None:
        problems.append(f"{path}:1: module {why}")
    for node in tree.body if top_level_only else ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_") and not node.name.startswith("__"):
                continue
            dunder_exempt = {"__init__", "__repr__", "__iter__", "__len__", "__enter__", "__exit__"}
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in dunder_exempt:
                continue
            if (why := _missing(node)) is not None:
                problems.append(f"{path}:{node.lineno}: {node.name} {why}")
    return problems


def main(argv: list[str]) -> int:
    """🇺🇸 Exit 1 when any source file breaks the rule. 🇧🇷 Sai com 1 quando algum arquivo quebra a regra."""
    roots = [Path(arg) for arg in argv] or [Path("apps/sdk"), Path("apps/cli"), Path("apps/api")]
    problems: list[str] = []
    for root in roots:
        # 🇺🇸 A package root is checked through `src/` (fully) and `tests/` (top level); any other folder as a whole.
        # 🇧🇷 A raiz de um pacote é checada pelo `src/` (inteiro) e `tests/` (nível de cima); outra pasta, inteira.
        python_root = root / "src" if (root / "src").is_dir() else root
        for path in sorted(python_root.rglob("*.py")):
            problems.extend(check(path))
        if python_root != root and (root / "tests").is_dir():
            for path in sorted((root / "tests").rglob("*.py")):
                problems.extend(check(path, top_level_only=True))
        native = root / "native"
        if native.is_dir():
            for sub in ("src", "tests"):
                for path in sorted((native / sub).rglob("*.rs")):
                    problems.extend(check_rust(path))
    for line in problems:
        print(line)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
