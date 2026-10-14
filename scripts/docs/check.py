"""`make docs-check`: everything the published docs promise, proven against the code in one run.

Fails (exit 1) when:

- a generated `docs/reference/*.json` differs from what `make docs` writes;
- `docs/site.json` breaks the contract (ids, sources and their `.pt-BR.md`
  twins, descriptions ≤ 160 chars in both locales, references);
- a page's twin does not share its skeleton (heading levels, code fences);
- a relative link, an anchor, or an absolute link into this repository
  does not resolve (the relative-link reading is `check_docs.links`, shared);
- a page has raw HTML outside a code fence (`markdown.raw_html`) — the site
  escapes HTML as text, so it would be published as a broken page;
- an image has an external URL outside a badge-only paragraph
  (`markdown.external_images`) — the site's CSP would not load it;
- a runnable ```` ```python ```` block fails in the sandbox (`snippets.py`);
- a `diagnos …` line in the docs names a command or flag that does not
  exist, or `diagnos … --help` disagrees with `cli.json` (`cli_check.py`);
- a generated page id breaks the site's `PAGE_ID` grammar or is generated twice.

The Markdown pages are documentation, not code, so they stay bilingual: every
`NAME.md` needs its `NAME.pt-BR.md` twin. The generated text is English-only
(see `l10n`), so there is no translation to check in the reference JSON.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from ..check_docs import is_relative, links
from . import cli_check, generate, site, snippets, urls
from .markdown import anchors, external_images, raw_html, structure
from .output import REPO_ROOT

_RAW_HTML = "raw HTML is not rendered by the site"
_EXTERNAL_IMAGE = "external image is blocked by the site's CSP"


def _repo_link(target: str, repo: str) -> str | None:
    """Returns the repository path of an absolute `…/blob|tree/<ref>/<path>` link to this repo, else `None`."""
    match = re.match(rf"^{re.escape(repo)}/(?:blob|tree)/[^/]+/(.*)$", target)
    return match[1] if match else None


def link_problems(path: str, root: Path, repo: str) -> list[str]:
    """Returns the dead files and dead anchors among the links of one page.

    Args:
        path: The page, relative to `root`.
        root: The repository root.
        repo: The repository URL from the manifest. An absolute link into it is checked like a relative one.
    """
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
            problems.append(f"{path}:{line}: dead link → {target}")
        elif anchor and resolved.suffix == ".md" and anchor.lower() not in anchors(resolved.read_text("utf-8")):
            problems.append(f"{path}:{line}: dead anchor → {target}")
    return problems


def page_problems(manifest: dict[str, Any], root: Path) -> tuple[list[str], int]:
    """Checks every manifest page: twin skeleton, links, raw HTML, external images and runnable snippets.

    Returns:
        The problem lines and the number of snippet blocks that ran.
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
            problems.append(f"{page.translation}:1: skeleton differs from {page.source}")
        for path in (page.source, page.translation):
            problems += link_problems(path, root, repo)
            text = (root / path).read_text(encoding="utf-8")
            problems += [f"{path}:{line}: {_RAW_HTML} → {tag}" for line, tag in raw_html(text)]
            problems += [f"{path}:{line}: {_EXTERNAL_IMAGE} → {url}" for line, url in external_images(text)]
            outcome = snippets.run_file(root / path, root)
            ran += outcome.ran
            problems += outcome.problems
    return problems, ran


def cli_problems(manifest: dict[str, Any], document: dict[str, Any], root: Path) -> tuple[list[str], int]:
    """Checks `--help` against `cli.json`, then every `diagnos …` line of the docs against the command tree.

    Returns:
        The problem lines and the number of `diagnos …` lines checked.
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


def reference_id_problems(manifest: dict[str, Any], root: Path) -> list[str]:
    """Returns the generated page ids that break `PAGE_ID` or collide; the site would build them exactly so."""
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
    """Runs every check and prints every problem.

    Returns:
        The process exit code: 1 when any check found a problem, else 0.
    """
    manifest = site.load(root)
    problems = site.check(manifest, root)
    problems += generate.stale(root)
    if not problems:
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
