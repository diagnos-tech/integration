"""`docs/site.json`: load it and hold it to the contract (`packages/devdocs/src/contract/siteManifest.ts`).

The manifest is the one hand-written file the site cannot render without,
and a mistake in it (a typo'd key, an id that breaks the URL grammar, a
page whose Portuguese twin is missing) would only surface when the site is
built in another repository. Every rule of the contract is checked here
instead, next to the file, in `make docs-check`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .output import REPO_ROOT

MANIFEST = "docs/site.json"
PAGE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$")
ROOT_PAGE_ID = "overview"
LOCALES = ["en", "pt-br"]
REFERENCE_KINDS = ("openapi", "cli", "sdk")
DESCRIPTION_MAX = 160
PT_SUFFIX = ".pt-BR.md"
_H1 = re.compile(r"^# \S", re.MULTILINE)
_TOP_KEYS = {"schemaVersion", "site", "locales", "nav", "reference", "redirects"}
_MARKDOWN_KEYS = {"id", "source", "description", "title"}
_REFERENCE_KEYS = {"id", "reference", "title"}


@dataclass(frozen=True)
class Page:
    """One Markdown page of the manifest: its id and its English file, whose `.pt-BR.md` twin is the translation."""

    id: str
    source: str

    @property
    def translation(self) -> str:
        """The `.pt-BR.md` twin of `source`."""
        return pt_twin(self.source)


def pt_twin(source: str) -> str:
    """Returns the Portuguese twin of an English page: `X.md` → `X.pt-BR.md`."""
    return source[: -len(".md")] + PT_SUFFIX


def load(root: Path = REPO_ROOT) -> dict[str, Any]:
    """Returns the parsed manifest of `root`, which must be a JSON object."""
    loaded = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "docs/site.json must be a JSON object"
    return loaded


def pages(manifest: dict[str, Any]) -> list[Page]:
    """Returns every Markdown page of the manifest, in navigation order."""
    return [
        Page(id=page["id"], source=page["source"])
        for group in manifest.get("nav", [])
        for page in group.get("pages", [])
        if "source" in page
    ]


def _l10n_problems(value: object, where: str, *, limit: int | None = None) -> list[str]:
    """Returns the problems of an `L10n`, which needs exactly `en` and `pt-br`, both non-empty and ≤ `limit`."""
    if not isinstance(value, dict) or sorted(value) != sorted(LOCALES):
        return [f"{where}: needs exactly {LOCALES}"]
    problems = []
    for locale in LOCALES:
        text = value[locale]
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{where}.{locale}: empty")
        elif limit is not None and len(text) > limit:
            problems.append(f"{where}.{locale}: {len(text)} chars > {limit}")
    return problems


def _page_problems(page: dict[str, Any], root: Path) -> list[str]:
    """Returns the problems of one navigation entry, Markdown or reference."""
    where = f"{MANIFEST}: page {page.get('id')!r}"
    page_id = page.get("id")
    if not isinstance(page_id, str) or not PAGE_ID.match(page_id):
        return [f"{where}: id does not match PAGE_ID"]
    if "reference" in page:
        extra = set(page) - _REFERENCE_KEYS
        problems = [f"{where}: unknown key(s) {sorted(extra)}"] if extra else []
        if page["reference"] not in REFERENCE_KINDS:
            problems.append(f"{where}: reference must be one of {REFERENCE_KINDS}")
        if "title" in page:
            problems += _l10n_problems(page["title"], f"{where}.title")
        return problems
    extra = set(page) - _MARKDOWN_KEYS
    problems = [f"{where}: unknown key(s) {sorted(extra)}"] if extra else []
    problems += _l10n_problems(page.get("description"), f"{where}.description", limit=DESCRIPTION_MAX)
    if "title" in page:
        problems += _l10n_problems(page["title"], f"{where}.title")
    source = page.get("source")
    if not isinstance(source, str) or not source.endswith(".md") or source.endswith(PT_SUFFIX):
        return [*problems, f"{where}: source must be the English .md"]
    for path in (source, pt_twin(source)):
        if not (root / path).is_file():
            problems.append(f"{where}: missing file → {path}")
        elif "title" not in page and not _H1.search((root / path).read_text(encoding="utf-8")):
            problems.append(f"{where}: {path} has no '# H1' and no title")
    return problems


def check(manifest: dict[str, Any], root: Path = REPO_ROOT) -> list[str]:
    """Returns every way the manifest breaks the contract, each as a `docs/site.json: what` line.

    Args:
        manifest: The parsed `docs/site.json`.
        root: The repository root, where the pages' source files and `.pt-BR.md` twins are looked up.
    """
    problems = [f"{MANIFEST}: unknown key(s) {sorted(set(manifest) - _TOP_KEYS)}"] if set(manifest) - _TOP_KEYS else []
    if manifest.get("schemaVersion") != 1:
        problems.append(f"{MANIFEST}: schemaVersion must be 1")
    site = manifest.get("site", {})
    if not isinstance(site, dict) or not site.get("name") or not str(site.get("repo", "")).startswith("https://"):
        problems.append(f"{MANIFEST}: site needs a name and an https repo URL")
    if manifest.get("locales") != LOCALES:
        problems.append(f"{MANIFEST}: locales must be {LOCALES}")
    references = manifest.get("reference", {})
    if not isinstance(references, dict) or sorted(references) != sorted(REFERENCE_KINDS):
        problems.append(f"{MANIFEST}: reference must map exactly {REFERENCE_KINDS}")
    ids: list[str] = []
    sources: list[str] = []
    used_kinds: list[str] = []
    for group in manifest.get("nav", []):
        problems += _l10n_problems(group.get("group"), f"{MANIFEST}: group")
        if not group.get("pages"):
            problems.append(f"{MANIFEST}: group {group.get('group')} has no pages")
        for page in group.get("pages", []):
            problems += _page_problems(page, root)
            ids.append(str(page.get("id")))
            if "source" in page:
                sources.append(str(page["source"]))
            if "reference" in page:
                used_kinds.append(str(page["reference"]))
    problems += [f"{MANIFEST}: duplicate id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    problems += [f"{MANIFEST}: duplicate source {s!r}" for s in sorted({s for s in sources if sources.count(s) > 1})]
    if sorted(used_kinds) != sorted(REFERENCE_KINDS):
        problems.append(f"{MANIFEST}: each reference kind must appear exactly once")
    if ROOT_PAGE_ID not in ids:
        problems.append(f"{MANIFEST}: the root page {ROOT_PAGE_ID!r} is required")
    reserved = [page["id"] for g in manifest.get("nav", []) for page in g.get("pages", []) if "reference" in page]
    for page_id in ids:
        for prefix in reserved:
            if page_id.startswith(f"{prefix}/"):
                problems.append(f"{MANIFEST}: id {page_id!r} is under the reference section {prefix!r}")
    for redirect in manifest.get("redirects", []):
        source_id, target = redirect.get("from"), redirect.get("to")
        if not (isinstance(source_id, str) and PAGE_ID.match(source_id)) or source_id in ids:
            problems.append(f"{MANIFEST}: redirect from {source_id!r} must be a free, valid id")
        if target not in ids:
            problems.append(f"{MANIFEST}: redirect to {target!r} is not a page")
    return problems
