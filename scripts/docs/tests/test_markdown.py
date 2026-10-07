"""🇺🇸 The Markdown the checks rely on is read the way GitHub reads it: fences, headings, anchors and raw HTML.

🇧🇷 O Markdown em que as checagens se apoiam é lido do jeito que o GitHub lê: cercas, títulos, âncoras e HTML cru.
"""

from __future__ import annotations

from scripts.docs.markdown import anchors, external_images, fences, headings, raw_html, slug, structure

PAGE = """# Title

- a list item with code:

  ```python no-run
  def f() -> None:
      pass
  ```

~~~sh
# not a heading
~~~

## `--json`, for scripts
## Datas e precisão de tempo
## Datas e precisão de tempo
<a id="custom-anchor"></a>
"""


def test_fences_carry_language_flags_line_and_dedented_body() -> None:
    """🇺🇸 A fence inside a list item loses the item's indentation. 🇧🇷 Uma cerca num item de lista perde a indentação."""
    python, shell = fences(PAGE)
    assert (python.language, python.flags, python.line) == ("python", ("no-run",), 6)
    assert python.body == "def f() -> None:\n    pass"
    assert (shell.language, shell.body) == ("sh", "# not a heading")


def test_headings_skip_fenced_lines() -> None:
    """🇺🇸 A `#` comment inside a fence is not a heading. 🇧🇷 Um comentário `#` numa cerca não é título."""
    assert [(level, text) for level, text, _ in headings(PAGE)] == [
        (1, "Title"),
        (2, "`--json`, for scripts"),
        (2, "Datas e precisão de tempo"),
        (2, "Datas e precisão de tempo"),
    ]


def test_slugs_follow_github() -> None:
    """🇺🇸 Lowercase, punctuation dropped, accents kept, link text kept. 🇧🇷 Minúsculas, pontuação fora, acentos ficam."""
    assert slug("`--json`, for scripts") == "--json-for-scripts"
    assert slug("7. Key and content envelope") == "7-key-and-content-envelope"
    assert slug("Datas e precisão de tempo") == "datas-e-precisão-de-tempo"
    assert slug("See [the guide](x.md) now") == "see-the-guide-now"


def test_anchors_deduplicate_and_ignore_html_ids() -> None:
    """🇺🇸 Repeats get `-1`; an `<a id>` is raw HTML, not an anchor. 🇧🇷 Repetições ganham `-1`; `<a id>` é HTML cru."""
    found = anchors(PAGE)
    assert {"title", "datas-e-precisão-de-tempo", "datas-e-precisão-de-tempo-1"} <= found
    assert "custom-anchor" not in found


def test_raw_html_outside_fences_and_inline_code_only() -> None:
    """🇺🇸 Tags and comments count; a fenced `<br/>`, a code span and an autolink do not.

    🇧🇷 Tags e comentários contam; um `<br/>` em cerca, um trecho de código e um autolink não.
    """
    assert raw_html(PAGE) == [(17, "<a>"), (17, "</a>")]
    page = (
        '<p align="center"><b>x</b></p>\n'
        "<!-- hidden -->\n"
        "Use `<br/>` in a label, see <https://example.com> or <dev@example.com>.\n"
        "```mermaid\n"
        'A["one<br/>two"]\n'
        "```\n"
        "Done.\n"
    )
    assert raw_html(page) == [(1, "<p>"), (1, "<b>"), (1, "</b>"), (1, "</p>"), (2, "<!--")]


def test_structure_is_the_skeleton_in_order() -> None:
    """🇺🇸 Heading levels and fence languages, as they appear. 🇧🇷 Níveis de título e linguagens, na ordem."""
    assert structure(PAGE) == ["h1", "```python", "```sh", "h2", "h2", "h2"]


def test_external_images_skip_badge_only_paragraphs() -> None:
    """🇺🇸 A badge block passes; an external image in prose, or next to prose, does not; relative images are fine.

    🇧🇷 Um bloco de badges passa; imagem externa na prosa, ou ao lado dela, não; imagem relativa é normal.
    """
    page = (
        "# Title\n"
        "\n"
        "[![CI](https://x.test/ci.svg)](https://x.test/ci)\n"
        "![License](https://x.test/lic.svg)\n"
        "\n"
        "See ![diagram](https://x.test/d.png) and ![local](images/d.png).\n"
        "\n"
        "![Coverage](https://x.test/cov.svg)\n"
        "Prose right after a badge makes it a normal paragraph.\n"
        "\n"
        "```md\n"
        "![in code](https://x.test/code.png)\n"
        "```\n"
    )
    assert external_images(page) == [(6, "https://x.test/d.png"), (8, "https://x.test/cov.svg")]
