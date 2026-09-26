"""🇺🇸 `docs/site.json` holds to the contract, and every way to break it is caught with a clear line.

🇧🇷 O `docs/site.json` segue o contrato, e todo jeito de quebrá-lo é pego com uma linha clara.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts.docs import site
from scripts.docs.output import REPO_ROOT


@pytest.fixture
def manifest() -> dict[str, Any]:
    """🇺🇸 A fresh copy of the committed manifest. 🇧🇷 Uma cópia nova do manifesto commitado."""
    return copy.deepcopy(site.load())


def first_page(manifest: dict[str, Any]) -> dict[str, Any]:
    """🇺🇸 The overview page entry. 🇧🇷 A entrada da página de visão geral."""
    page: dict[str, Any] = manifest["nav"][0]["pages"][0]
    return page


def _without_title_or_h1(manifest: dict[str, Any]) -> None:
    """🇺🇸 The root page pointed at a fixture with no `# H1`, and no `title` to fall back on.

    🇧🇷 A página raiz apontando para uma fixture sem `# H1`, e sem `title` para cair.
    """
    page = first_page(manifest)
    page.pop("title")
    page["source"] = "scripts/docs/tests/fixtures/no-h1.md"


def test_the_committed_manifest_is_valid(manifest: dict[str, Any]) -> None:
    """🇺🇸 No problem at all, and every page is a markdown pair. 🇧🇷 Nenhum problema, e toda página é um par."""
    assert site.check(manifest) == []
    pages = site.pages(manifest)
    assert pages[0].id == site.ROOT_PAGE_ID
    assert all((REPO_ROOT / page.translation).is_file() for page in pages)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda m: first_page(m).update(id="Bad_Id"), "id does not match PAGE_ID"),
        (lambda m: m["nav"][1]["pages"][0].update(id="quickstart"), "duplicate id"),
        (lambda m: first_page(m)["description"].update(en="x" * 161), "161 chars > 160"),
        (lambda m: first_page(m)["description"].pop("pt-br"), "needs exactly"),
        (lambda m: first_page(m).update(source="docs/nope.md"), "missing file"),
        (lambda m: first_page(m).update(source="README.pt-BR.md"), "source must be the English .md"),
        (lambda m: first_page(m).update(desciption={}), "unknown key"),
        (
            _without_title_or_h1,
            "has no '# H1' and no title",
        ),
        (lambda m: m["redirects"].append({"from": "old", "to": "nowhere"}), "is not a page"),
        (lambda m: m["nav"][1]["pages"][0].update(id="sdk/reference/intro"), "is under the reference section"),
        (lambda m: m.update(locales=["en"]), "locales must be"),
        (lambda m: m["reference"].pop("cli"), "reference must map exactly"),
    ],
)
def test_each_contract_rule_is_enforced(
    manifest: dict[str, Any], mutate: Callable[[dict[str, Any]], object], expected: str
) -> None:
    """🇺🇸 One mutation, one named problem. 🇧🇷 Uma mutação, um problema nomeado."""
    mutate(manifest)
    problems = site.check(manifest)
    assert any(expected in problem for problem in problems), problems


def test_a_page_without_its_twin_is_refused(manifest: dict[str, Any], tmp_path: Path) -> None:
    """🇺🇸 An English file alone is not a page. 🇧🇷 Um arquivo em inglês sozinho não é uma página."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "alone.md").write_text("# Alone\n", encoding="utf-8")
    manifest["nav"] = [
        {
            "group": {"en": "G", "pt-br": "G"},
            "pages": [{"id": "overview", "source": "docs/alone.md", "description": {"en": "d", "pt-br": "d"}}],
        }
    ]
    problems = site.check(manifest, root=tmp_path)
    assert any("docs/alone.pt-BR.md" in problem for problem in problems)
