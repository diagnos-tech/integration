"""🇺🇸 `split_bilingual` must agree with the site's `splitBilingual` on every case, edge cases included.

The first three tests are `l10n.test.ts`, case for case; the rest pin what
JavaScript's `trim()` does and Python's `strip()` does not.

🇧🇷 `split_bilingual` precisa concordar com o `splitBilingual` do site em todo caso, inclusive os de borda.

Os três primeiros testes são o `l10n.test.ts`, caso a caso; o resto fixa o
que o `trim()` do JavaScript faz e o `strip()` do Python não faz.
"""

from __future__ import annotations

import pytest

from scripts.docs.bilingual import BilingualSplit, js_trim, l10n_field, split_bilingual, split_cli_help


def test_both_markers_in_either_order() -> None:
    """🇺🇸 Both markers, both orders (`l10n.test.ts`). 🇧🇷 Os dois marcadores, nas duas ordens (`l10n.test.ts`)."""
    assert split_bilingual("🇺🇸 List patients.\n\n🇧🇷 Lista pacientes.") == BilingualSplit(
        "List patients.", "Lista pacientes.", untranslated=False
    )
    assert split_bilingual("🇧🇷 Lista. 🇺🇸 List.") == BilingualSplit("List.", "Lista.", untranslated=False)


def test_no_marker_gives_the_whole_text_to_both_and_flags_it() -> None:
    """🇺🇸 No marker: whole text, untranslated. 🇧🇷 Sem marcador: texto inteiro, sem tradução."""
    assert split_bilingual("  plain  ") == BilingualSplit("plain", "plain", untranslated=True)


def test_one_side_only_is_inherited_by_the_other() -> None:
    """🇺🇸 One side marked: the other inherits it. 🇧🇷 Um lado marcado: o outro herda."""
    assert split_bilingual("🇺🇸 Only english") == BilingualSplit("Only english", "Only english", untranslated=False)
    assert split_bilingual("🇧🇷 Só português") == BilingualSplit("Só português", "Só português", untranslated=False)


def test_first_occurrence_wins_like_index_of() -> None:
    """🇺🇸 `indexOf` semantics: a repeated marker belongs to the later segment. 🇧🇷 Semântica do `indexOf`."""
    assert split_bilingual("🇺🇸 a 🇧🇷 b 🇺🇸 c") == BilingualSplit("a", "b 🇺🇸 c", untranslated=False)


@pytest.mark.parametrize(
    ("raw", "trimmed"),
    [
        ("﻿ text ﻿", "text"),  # 🇺🇸 ZWNBSP is JS whitespace 🇧🇷 ZWNBSP é espaço no JS
        ("  text　", "text"),  # 🇺🇸 Zs characters 🇧🇷 caracteres Zs
        (" text ", "text"),  # 🇺🇸 line terminators 🇧🇷 terminadores de linha
        ("\x1ctext\x1f", "\x1ctext\x1f"),  # 🇺🇸 Python strips these, JS does not 🇧🇷 o Python apara, o JS não
        ("\x85text", "\x85text"),  # 🇺🇸 NEL: not JS whitespace 🇧🇷 NEL: não é espaço no JS
    ],
)
def test_trim_is_javascripts(raw: str, trimmed: str) -> None:
    """🇺🇸 `js_trim` removes exactly what `String.prototype.trim()` removes. 🇧🇷 O mesmo que o `trim()` do JS."""
    assert js_trim(raw) == trimmed
    assert split_bilingual(raw).en == trimmed


def test_cli_help_splits_on_one_middle_dot() -> None:
    """🇺🇸 `EN · PT` splits; markers win; two dots are ambiguous. 🇧🇷 `EN · PT` divide; dois pontos são ambíguos."""
    assert split_cli_help("Patients · Pacientes") == BilingualSplit("Patients", "Pacientes", untranslated=False)
    assert split_cli_help("🇺🇸 A · B 🇧🇷 C") == BilingualSplit("A · B", "C", untranslated=False)
    assert split_cli_help("a · b · c").untranslated
    assert split_cli_help("Overrides DIAGNOS_VAULT_URL").untranslated


def test_absent_text_is_undocumented_not_untranslated() -> None:
    """🇺🇸 `None` or blank asks the site for nothing. 🇧🇷 `None` ou vazio não pede nada ao site."""
    assert l10n_field(None) == ({"en": "", "pt-br": ""}, False)
    assert l10n_field("  ") == ({"en": "", "pt-br": ""}, False)
    assert l10n_field("x") == ({"en": "x", "pt-br": "x"}, True)
    assert l10n_field("A · B", cli=True) == ({"en": "A", "pt-br": "B"}, False)
