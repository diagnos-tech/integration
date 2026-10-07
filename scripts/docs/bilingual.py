"""🇺🇸 The bilingual split rule, a line-for-line port of the site's `splitBilingual` (`l10n.ts`).

Every generated JSON carries text as `{"en": …, "pt-br": …}`, and the site
splits OpenAPI `summary`/`description` itself with the same rule. Two
implementations of one rule only stay one rule if they agree on every edge
case, so this mirrors the TypeScript exactly — including what JavaScript's
`String.prototype.trim()` counts as whitespace, which is not what Python's
`str.strip()` counts (U+FEFF is trimmed there, U+001C–U+001F and U+0085
are not). `tests/test_bilingual.py` pins those cases.

The CLI writes its help as `English · Português` — what a terminal shows
both audiences at once — so `split_cli_help` reads that form too; it is a
generator convention for `cli.json` only, never applied to the OpenAPI text
the site splits on its own.

🇧🇷 A regra de divisão bilíngue, um porte linha a linha do `splitBilingual` do site (`l10n.ts`).

Todo JSON gerado carrega texto como `{"en": …, "pt-br": …}`, e o site divide
o `summary`/`description` do OpenAPI sozinho com a mesma regra. Duas
implementações de uma regra só continuam uma regra se concordam em todo caso
de borda, então isto espelha o TypeScript ao pé da letra — inclusive o que o
`String.prototype.trim()` do JavaScript conta como espaço, que não é o que o
`str.strip()` do Python conta (U+FEFF é aparado lá, U+001C–U+001F e U+0085
não). `tests/test_bilingual.py` fixa esses casos.

A CLI escreve a ajuda como `English · Português` — o que um terminal mostra
aos dois públicos de uma vez — então `split_cli_help` lê essa forma também; é
uma convenção do gerador só para o `cli.json`, nunca aplicada ao texto do
OpenAPI que o site divide sozinho.
"""

from __future__ import annotations

from dataclasses import dataclass

EN_FLAG = "🇺🇸"
PT_FLAG = "🇧🇷"
CLI_SEPARATOR = " · "

# 🇺🇸 ECMAScript WhiteSpace (Zs plus TAB, VT, FF, ZWNBSP) and LineTerminator — exactly what `trim()` removes.
# 🇧🇷 WhiteSpace do ECMAScript (Zs mais TAB, VT, FF, ZWNBSP) e LineTerminator — exatamente o que `trim()` remove.
_JS_WHITESPACE = "\t\n\v\f\r                  　﻿"


@dataclass(frozen=True)
class BilingualSplit:
    """🇺🇸 One text in both locales; `untranslated` when it carried no marker at all.

    🇧🇷 Um texto nos dois locales; `untranslated` quando não trazia marcador nenhum.
    """

    en: str
    pt_br: str
    untranslated: bool

    def l10n(self) -> dict[str, str]:
        """🇺🇸 The contract's `L10n` shape. 🇧🇷 A forma `L10n` do contrato."""
        return {"en": self.en, "pt-br": self.pt_br}


def js_trim(text: str) -> str:
    """🇺🇸 `String.prototype.trim()`, not `str.strip()` — see the module docstring.

    🇧🇷 `String.prototype.trim()`, não `str.strip()` — ver a docstring do módulo.
    """
    return text.strip(_JS_WHITESPACE)


def split_bilingual(text: str) -> BilingualSplit:
    """🇺🇸 From `🇺🇸` to `🇧🇷` is English, from `🇧🇷` on is Portuguese; either order; no marker → both get it all.

    A side with no marker of its own inherits the other side, so a page is
    never empty.

    🇧🇷 Do `🇺🇸` até o `🇧🇷` é inglês, do `🇧🇷` em diante é português; qualquer ordem; sem marcador → os dois recebem tudo.

    Um lado sem marcador próprio herda o outro, para uma página nunca ficar
    vazia.
    """
    en_index = text.find(EN_FLAG)
    pt_index = text.find(PT_FLAG)
    if en_index == -1 and pt_index == -1:
        whole = js_trim(text)
        return BilingualSplit(en=whole, pt_br=whole, untranslated=True)

    def segment(start: int, flag: str, other_index: int) -> str:
        """🇺🇸 The text after `flag` up to the other marker (when it comes later) or the end.

        🇧🇷 O texto depois de `flag` até o outro marcador (quando vem depois) ou o fim.
        """
        if start == -1:
            return ""
        end = other_index if other_index > start else len(text)
        return js_trim(text[start + len(flag) : end])

    en = segment(en_index, EN_FLAG, pt_index)
    pt = segment(pt_index, PT_FLAG, en_index)
    return BilingualSplit(en=en or pt, pt_br=pt or en, untranslated=False)


def split_cli_help(text: str) -> BilingualSplit:
    """🇺🇸 A CLI help string: markers win; else exactly one `" · "` splits English from Portuguese.

    More than one separator is ambiguous (which dot is the boundary?), so it
    falls through to `split_bilingual` and is reported as untranslated.

    🇧🇷 Uma string de ajuda da CLI: marcadores vencem; senão, exatamente um `" · "` separa inglês de português.

    Mais de um separador é ambíguo (qual ponto é a fronteira?), então cai em
    `split_bilingual` e é reportado como não traduzido.
    """
    if EN_FLAG in text or PT_FLAG in text or text.count(CLI_SEPARATOR) != 1:
        return split_bilingual(text)
    en, pt = text.split(CLI_SEPARATOR)
    return BilingualSplit(en=js_trim(en), pt_br=js_trim(pt), untranslated=False)


def l10n_field(text: str | None, *, cli: bool = False) -> tuple[dict[str, str], bool]:
    """🇺🇸 `(L10n, untranslated)` for an optional text; absent or blank text is undocumented, not untranslated.

    An empty `{"en": "", "pt-br": ""}` asks the site for nothing, so it
    carries no `untranslated` flag — a warning about a translation that
    was never needed would be noise.

    🇧🇷 `(L10n, untranslated)` de um texto opcional; texto ausente ou em branco é não documentado, não não traduzido.

    Um `{"en": "", "pt-br": ""}` vazio não pede nada ao site, então não leva
    a flag `untranslated` — um aviso sobre uma tradução que nunca foi
    necessária seria ruído.
    """
    if text is None or not js_trim(text):
        return {"en": "", "pt-br": ""}, False
    split = split_cli_help(text) if cli else split_bilingual(text)
    return split.l10n(), split.untranslated
