"""The generated reference carries one English text in both locales, in the pair shape the site reads."""

from __future__ import annotations

import pytest

from scripts.docs.l10n import l10n_field
from scripts.docs.site import LOCALES


def test_the_same_english_text_goes_to_every_locale() -> None:
    """The pair has exactly the contract's locales, each holding the text unchanged."""
    pair = l10n_field("List patients.")
    assert sorted(pair) == sorted(LOCALES)
    assert pair == {"en": "List patients.", "pt-br": "List patients."}


@pytest.mark.parametrize("text", ["  padded\n", "\tpadded  ", "padded"])
def test_surrounding_whitespace_is_removed(text: str) -> None:
    """Docstring and help strings often end in a newline; the reference never does."""
    assert l10n_field(text) == {"en": "padded", "pt-br": "padded"}


def test_inner_text_is_kept_as_written() -> None:
    """Paragraph breaks, the middle dot and non-ASCII characters are content, not markup."""
    text = "A · B\n\nSecond paragraph — with a dash."
    assert l10n_field(text) == {"en": text, "pt-br": text}


@pytest.mark.parametrize("text", [None, "", "  ", "\n\t"])
def test_absent_or_blank_text_is_an_empty_pair(text: str | None) -> None:
    """Undocumented asks the site for nothing: both locales are empty strings."""
    assert l10n_field(text) == {"en": "", "pt-br": ""}
