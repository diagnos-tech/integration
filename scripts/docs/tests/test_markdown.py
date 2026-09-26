"""🇺🇸 The Markdown the checks rely on is read the way GitHub reads it: fences, headings and anchors.

🇧🇷 O Markdown em que as checagens se apoiam é lido do jeito que o GitHub lê: cercas, títulos e âncoras.
"""

from __future__ import annotations

from scripts.docs.markdown import anchors, fences, headings, slug, structure

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


def test_anchors_deduplicate_and_include_html_ids() -> None:
    """🇺🇸 Repeats get `-1`, and `<a id>` counts. 🇧🇷 Repetições ganham `-1`, e `<a id>` conta."""
    found = anchors(PAGE)
    assert {"title", "datas-e-precisão-de-tempo", "datas-e-precisão-de-tempo-1", "custom-anchor"} <= found


def test_structure_is_the_skeleton_in_order() -> None:
    """🇺🇸 Heading levels and fence languages, as they appear. 🇧🇷 Níveis de título e linguagens, na ordem."""
    assert structure(PAGE) == ["h1", "```python", "```sh", "h2", "h2", "h2"]
