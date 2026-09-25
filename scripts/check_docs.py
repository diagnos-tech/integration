"""🇺🇸 Guard for the documentation rule: one file per language, always in pairs, never a dead relative link.

Every Markdown document ships as `NAME.md` (English) next to
`NAME.pt-BR.md` (Brazilian Portuguese). This script fails when:

- a document has no sibling in the other language;
- a document does not link to its sibling (the language switcher on top);
- a relative link or image points at a file that does not exist.

Files GitHub renders in a fixed place and that are not documentation (issue
and pull request templates, the changelog) are exempt. Run:
`uv run python scripts/check_docs.py` (part of `make lint`).

🇧🇷 Guarda da regra de documentação: um arquivo por língua, sempre em par, nunca um link relativo morto.

Todo documento Markdown sai como `NOME.md` (inglês) ao lado de
`NOME.pt-BR.md` (português do Brasil). Este script falha quando:

- um documento não tem o irmão na outra língua;
- um documento não aponta para o irmão (o seletor de idioma no topo);
- um link ou imagem relativo aponta para um arquivo que não existe.

Arquivos que o GitHub renderiza num lugar fixo e que não são documentação
(templates de issue e pull request, o changelog) ficam de fora. Rode:
`uv run python scripts/check_docs.py` (parte do `make lint`).
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
    """🇺🇸 Tracked and not-ignored `.md` files, relative to `root`. 🇧🇷 Arquivos `.md` versionados e não ignorados."""
    output = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted({Path(line) for line in output.splitlines() if line and (root / line).exists()})


def sibling(path: Path) -> Path:
    """🇺🇸 The same document in the other language. 🇧🇷 O mesmo documento na outra língua."""
    if path.name.endswith(PT_SUFFIX):
        return path.with_name(path.name[: -len(PT_SUFFIX)] + ".md")
    return path.with_name(path.name[: -len(".md")] + PT_SUFFIX)


def links(text: str) -> list[tuple[int, str]]:
    """🇺🇸 `(line, target)` of every link outside code fences. 🇧🇷 `(linha, alvo)` de todo link fora de código."""
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
    """🇺🇸 A link to a file in this repository (not a URL, not a pure anchor). 🇧🇷 Um link para arquivo deste repo."""
    return not re.match(r"^([a-z][a-z0-9+.-]*:|#|//)", target, flags=re.IGNORECASE)


def check(root: Path) -> list[str]:
    """🇺🇸 Every problem, as `file:line: what`. 🇧🇷 Todo problema, como `arquivo:linha: o quê`."""
    problems: list[str] = []
    for path in markdown_files(root):
        text = (root / path).read_text(encoding="utf-8")
        for number, target in links(text):
            if not is_relative(target):
                continue
            file_part = target.split("#", 1)[0].split("?", 1)[0]
            if file_part and not (root / path.parent / file_part).exists():
                problems.append(f"{path}:{number}: dead link · link morto → {target}")
        if EXEMPT.match(path.as_posix()):
            continue
        other = sibling(path)
        if not (root / other).exists():
            problems.append(f"{path}:1: missing translation · falta a tradução → {other}")
        elif f"]({other.name})" not in text and f"]({other.name}#" not in text:
            problems.append(f"{path}:1: no language switcher to · sem seletor de idioma para → {other.name}")
    return problems


def main() -> int:
    """🇺🇸 Exit 1 when any document breaks the rule. 🇧🇷 Sai com 1 quando algum documento quebra a regra."""
    root = Path(__file__).resolve().parent.parent
    problems = check(root)
    for line in problems:
        print(line)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
