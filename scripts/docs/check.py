"""🇺🇸 `make docs-check`: everything the published docs promise, proven against the code in one run.

Fails (exit 1) when:

- a generated `docs/reference/*.json` differs from what `make docs` writes;
- `docs/site.json` breaks the contract (ids, sources and their `.pt-BR.md`
  twins, descriptions ≤ 160 chars in both locales, references);
- a page's twin does not share its skeleton (heading levels, code fences);
- a relative link, an anchor, or an absolute link into this repository
  does not resolve (the relative-link reading is `check_docs.links`, shared);
- a runnable ```` ```python ```` block fails in the sandbox (`snippets.py`);
- a `diagnos …` line in the docs names a command or flag that does not
  exist, or `diagnos … --help` disagrees with `cli.json` (`cli_check.py`);
- any generated text is untranslated (no 🇺🇸/🇧🇷, or no `EN · PT` in the CLI).

🇧🇷 `make docs-check`: tudo que a doc publicada promete, provado contra o código numa rodada.

Falha (sai com 1) quando:

- um `docs/reference/*.json` gerado difere do que o `make docs` grava;
- o `docs/site.json` quebra o contrato (ids, sources e os gêmeos
  `.pt-BR.md`, descrições ≤ 160 caracteres nos dois locales, referências);
- o gêmeo de uma página não tem o mesmo esqueleto (níveis de título, blocos);
- um link relativo, uma âncora, ou um link absoluto para este repositório
  não resolve (a leitura de link relativo é `check_docs.links`, compartilhada);
- um bloco ```` ```python ```` executável falha no sandbox (`snippets.py`);
- uma linha `diagnos …` da doc nomeia comando ou flag que não existe, ou o
  `diagnos … --help` diverge do `cli.json` (`cli_check.py`);
- algum texto gerado está sem tradução (sem 🇺🇸/🇧🇷, ou sem `EN · PT` na CLI).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from ..check_docs import is_relative, links
from . import cli_check, generate, openapi, sdk, site, snippets, urls
from .markdown import anchors, structure
from .output import REPO_ROOT


def _repo_link(target: str, repo: str) -> str | None:
    """🇺🇸 The repository path of an absolute `…/blob|tree/<ref>/<path>` link to this repo, else `None`.

    🇧🇷 O caminho no repositório de um link absoluto `…/blob|tree/<ref>/<caminho>` para este repo, senão `None`.
    """
    match = re.match(rf"^{re.escape(repo)}/(?:blob|tree)/[^/]+/(.*)$", target)
    return match[1] if match else None


def link_problems(path: str, root: Path, repo: str) -> list[str]:
    """🇺🇸 Dead files and dead anchors among the links of one page. 🇧🇷 Arquivos e âncoras mortos de uma página."""
    text = (root / path).read_text(encoding="utf-8")
    problems = []
    for line, target in links(text):
        in_repo = _repo_link(target, repo)
        if in_repo is None and not is_relative(target):
            continue
        file_part, _, anchor = (in_repo if in_repo is not None else target).partition("#")
        base = root if in_repo is not None else (root / path).parent
        resolved = (base / file_part.split("?", 1)[0]) if file_part else root / path
        if not resolved.exists():
            problems.append(f"{path}:{line}: dead link · link morto → {target}")
        elif anchor and resolved.suffix == ".md" and anchor.lower() not in anchors(resolved.read_text("utf-8")):
            problems.append(f"{path}:{line}: dead anchor · âncora morta → {target}")
    return problems


def page_problems(manifest: dict[str, Any], root: Path) -> tuple[list[str], int]:
    """🇺🇸 Structure parity, links and snippets of every manifest page; returns the problems and blocks run.

    🇧🇷 Paridade de estrutura, links e snippets de toda página do manifesto; devolve os problemas e blocos rodados.
    """
    problems: list[str] = []
    ran = 0
    repo = manifest["site"]["repo"]
    for page in site.pages(manifest):
        if not (root / page.source).is_file() or not (root / page.translation).is_file():
            continue
        english = structure((root / page.source).read_text(encoding="utf-8"))
        portuguese = structure((root / page.translation).read_text(encoding="utf-8"))
        if english != portuguese:
            problems.append(f"{page.translation}:1: skeleton differs from · esqueleto difere de {page.source}")
        for path in (page.source, page.translation):
            problems += link_problems(path, root, repo)
            outcome = snippets.run_file(root / path, root)
            ran += outcome.ran
            problems += outcome.problems
    return problems, ran


def cli_problems(manifest: dict[str, Any], document: dict[str, Any], root: Path) -> tuple[list[str], int]:
    """🇺🇸 `--help` parity plus every `diagnos …` line of the docs; returns problems and lines checked.

    🇧🇷 Paridade do `--help` mais toda linha `diagnos …` da doc; devolve problemas e linhas checadas.
    """
    problems = cli_check.help_problems(document)
    checked = 0
    for page in site.pages(manifest):
        for path in (page.source, page.translation):
            if not (root / path).is_file():
                continue
            for line, command in cli_check.command_lines((root / path).read_text(encoding="utf-8")):
                checked += 1
                why = cli_check.usage_problem(command, document)
                if why:
                    problems.append(f"{path}:{line}: {why}")
    return problems, checked


def untranslated(references: dict[str, str], root: Path) -> list[str]:
    """🇺🇸 Every generated text the site would show untranslated. 🇧🇷 Todo texto gerado que sairia sem tradução."""
    read = {kind: json.loads((root / path).read_text(encoding="utf-8")) for kind, path in references.items()}
    found = [f"openapi: {where}" for where in openapi.untranslated(read["openapi"])]
    found += [f"cli: diagnos {' '.join(c['path'])}" for c in read["cli"]["commands"] if c.get("untranslated")]
    found += [f"sdk: {name}" for name in sdk.untranslated(read["sdk"])]
    return [f"{references['openapi'].rsplit('/', 1)[0]}: untranslated · sem tradução — {item}" for item in found]


def reference_id_problems(manifest: dict[str, Any], root: Path) -> list[str]:
    """🇺🇸 Generated page ids that break `PAGE_ID` or collide — the site would build them exactly so.

    🇧🇷 Ids de página gerados que quebram o `PAGE_ID` ou colidem — o site os montaria exatamente assim.
    """
    problems = []
    sections = [page for group in manifest["nav"] for page in group["pages"] if "reference" in page]
    for page in sections:
        path = manifest["reference"][page["reference"]]
        document = json.loads((root / path).read_text(encoding="utf-8"))
        ids = urls.reference_ids(page["id"], page["reference"], document)
        problems += [f"{path}: page id {i!r} breaks PAGE_ID" for i in ids if not site.PAGE_ID.match(i)]
        problems += [f"{path}: page id {i!r} is generated twice" for i in sorted({i for i in ids if ids.count(i) > 1})]
    return problems


def main(root: Path = REPO_ROOT) -> int:
    """🇺🇸 Runs every check, prints every problem, exits 1 on any. 🇧🇷 Roda tudo, imprime, sai com 1 se houve algum."""
    manifest = site.load(root)
    problems = site.check(manifest, root)
    problems += generate.stale(root)
    if not problems:
        problems += untranslated(manifest["reference"], root)
        problems += reference_id_problems(manifest, root)
    page_found, ran = page_problems(manifest, root)
    cli_document = json.loads((root / manifest["reference"]["cli"]).read_text(encoding="utf-8"))
    cli_found, lines = cli_problems(manifest, cli_document, root)
    problems += page_found + cli_found
    for line in problems:
        print(line)
    pages = len(site.pages(manifest))
    print(f"{pages} pages × 2 locales · {ran} snippets run · {lines} CLI lines · {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
