"""The `{"en", "pt-br"}` text pair that every generated reference JSON carries.

The published developer site reads each generated text as an `L10n` pair, one
string per locale, so the schema of `docs/reference/*.json` is a contract with
that site and keeps the pair. The code base is English-only, so a generated
text has one language and is written to both locales unchanged. That is what
the site's own `splitBilingual` does with text that has no locale markers (the
whole text goes to both locales), the case OpenAPI `summary`/`description`
strings now fall into.

The Markdown guides are the exception: they are documentation, not code, and
stay in `NAME.md` + `NAME.pt-BR.md` pairs (`site.Page`).
"""

from __future__ import annotations

from .site import LOCALES


def l10n_field(text: str | None) -> dict[str, str]:
    """Returns an optional English text as the contract's `L10n` pair, the same text in every locale.

    Args:
        text: A docstring or help string. `None` or blank means undocumented.

    Returns:
        `{"en": text, "pt-br": text}` with the surrounding whitespace removed. Both values are empty when `text` is
        absent or blank, which asks the site for nothing.
    """
    value = (text or "").strip()
    return {locale: value for locale in LOCALES}
