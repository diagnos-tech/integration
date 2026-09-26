"""🇺🇸 Just enough Markdown for the checks: fenced blocks, headings, GitHub's anchor slugs and raw HTML.

Not a Markdown parser — the site has a real one. These are the facts the
checks need, read the way GitHub reads them (the repository has to stay
readable there without the site): a fence opens with three or more
backticks or tildes and closes with the same character, at least as long;
a heading is `#`… outside a fence; an anchor is GitHub's slug of the
heading text, with `-1`, `-2`… on repeats; raw HTML is any tag or comment
outside a fence and outside inline code — the site never renders HTML (it
escapes it as text), so a page must not contain any.

🇧🇷 Só o Markdown que as checagens precisam: blocos cercados, títulos, os slugs de âncora do GitHub e HTML cru.

Não é um parser de Markdown — o site tem um de verdade. São os fatos que as
checagens precisam, lidos do jeito que o GitHub os lê (o repositório
precisa continuar legível lá sem o site): uma cerca abre com três ou mais
crases ou tils e fecha com o mesmo caractere, no mínimo do mesmo tamanho;
um título é `#`… fora de cerca; uma âncora é o slug do GitHub para o texto
do título, com `-1`, `-2`… nas repetições; HTML cru é qualquer tag ou
comentário fora de cerca e fora de código inline — o site nunca renderiza
HTML (escapa como texto), então uma página não pode ter nenhum.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_OPEN = re.compile(r"^(?P<indent> *)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_HEADING = re.compile(r"^(?P<marks>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_INLINE_CODE = re.compile(r"`+[^`]*`+")
# A tag (`<b>`, `</p>`, `<br/>`, `<img …>`) or a comment. An autolink
# (`<https://…>`, `<user@host>`) has `:`/`@` right after the name, so the
# name must be followed by whitespace, `/` or `>` to count as a tag.
_RAW_HTML = re.compile(r"<!--|</?[A-Za-z][A-Za-z0-9-]*(?=[\s/>])[^<>]*>")
_EXTERNAL_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?(?P<url>[A-Za-z][A-Za-z0-9+.-]*:[^)\s>]+)")
# A badge: an image, or a link whose whole content is an image — `[![CI](svg)](url)`.
_BADGE = re.compile(r"\[?!\[[^\]]*\]\([^)]*\)(?:\]\([^)]*\))?")
_SLUG_DROP = re.compile(r"[^\w\- ]")


@dataclass(frozen=True)
class Fence:
    """🇺🇸 One fenced code block: its language, the rest of the info string, and where its body starts.

    🇧🇷 Um bloco de código cercado: a linguagem, o resto da info string e onde o corpo começa.
    """

    language: str
    flags: tuple[str, ...]
    line: int
    body: str


def fences(text: str) -> list[Fence]:
    """🇺🇸 Every fenced block, in order; `line` is the 1-based line of the first body line.

    A fence indented inside a list item has its body dedented by the same
    amount, as CommonMark does — the code is what the reader sees.

    🇧🇷 Todo bloco cercado, em ordem; `line` é a linha (a partir de 1) da primeira linha do corpo.

    Uma cerca indentada dentro de um item de lista tem o corpo desindentado
    na mesma medida, como o CommonMark faz — o código é o que quem lê vê.
    """
    found: list[Fence] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        opening = _OPEN.match(lines[index])
        if opening is None or (opening["fence"][0] == "`" and "`" in opening["info"]):
            index += 1
            continue
        marker, words, indent = opening["fence"], opening["info"].split(), len(opening["indent"])
        body: list[str] = []
        index += 1
        start = index + 1
        while index < len(lines):
            stripped = lines[index].strip()
            if stripped.startswith(marker[0] * len(marker)) and not stripped.strip(marker[0]):
                break
            line = lines[index]
            body.append(line[min(indent, len(line) - len(line.lstrip(" "))) :])
            index += 1
        found.append(Fence(words[0] if words else "", tuple(words[1:]), start, "\n".join(body)))
        index += 1
    return found


def outside_fences(text: str) -> list[tuple[int, str]]:
    """🇺🇸 `(line, text)` of every line not inside a fence. 🇧🇷 `(linha, texto)` de toda linha fora de cerca."""
    inside: set[int] = set()
    for fence in fences(text):
        inside.update(range(fence.line - 1, fence.line + fence.body.count("\n") + 2))
    return [(number, line) for number, line in enumerate(text.splitlines(), start=1) if number not in inside]


def headings(text: str) -> list[tuple[int, str, int]]:
    """🇺🇸 `(level, text, line)` of every ATX heading outside fences. 🇧🇷 `(nível, texto, linha)` de todo título ATX."""
    found = []
    for number, line in outside_fences(text):
        match = _HEADING.match(line)
        if match:
            found.append((len(match["marks"]), match["text"], number))
    return found


def slug(title: str) -> str:
    """🇺🇸 GitHub's anchor for a heading: link text kept, lowercased, punctuation dropped, spaces to `-`.

    🇧🇷 A âncora do GitHub para um título: texto de link mantido, minúsculas, pontuação fora, espaço vira `-`.
    """
    text = _LINK.sub(lambda match: match[1], title)
    return _SLUG_DROP.sub("", text.lower()).replace(" ", "-")


def anchors(text: str) -> set[str]:
    """🇺🇸 Every anchor a link may target in `text`: heading slugs, deduplicated GitHub's way.

    Only headings: an `<a id>` would be raw HTML (`raw_html`), which the site
    escapes — a link to it would pass here and 404 there.

    🇧🇷 Toda âncora que um link pode mirar em `text`: slugs de título, desduplicados como o GitHub.

    Só títulos: um `<a id>` seria HTML cru (`raw_html`), que o site escapa — um
    link para ele passaria aqui e daria 404 lá.
    """
    seen: dict[str, int] = {}
    found: set[str] = set()
    for _, title, _ in headings(text):
        base = slug(title)
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def paragraphs(text: str) -> list[list[tuple[int, str]]]:
    """🇺🇸 Runs of consecutive non-blank lines outside fences — a paragraph, as far as the checks care.

    🇧🇷 Sequências de linhas não vazias consecutivas fora de cerca — um parágrafo, no que importa às checagens.
    """
    found: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for number, line in outside_fences(text):
        if line.strip() == "" or (current and number != current[-1][0] + 1):
            if current:
                found.append(current)
            current = []
        if line.strip() != "":
            current.append((number, line))
    if current:
        found.append(current)
    return found


def external_images(text: str) -> list[tuple[int, str]]:
    """🇺🇸 `(line, url)` of every image with an absolute URL, except inside a paragraph made only of badges.

    The site only loads images from its own origin, so an external image is
    a broken image on the published page — images are files in this
    repository, linked by relative path. The badge block at the top of a
    README is the one exception, and only because the site drops that
    paragraph entirely (it is GitHub decoration, not documentation).

    🇧🇷 `(linha, url)` de toda imagem com URL absoluta, exceto num parágrafo feito só de badges.

    O site só carrega imagem da própria origem, então uma imagem externa é
    uma imagem quebrada na página publicada — imagem é arquivo deste
    repositório, por caminho relativo. O bloco de badges no topo de um README
    é a única exceção, e só porque o site descarta esse parágrafo inteiro (é
    decoração do GitHub, não documentação).
    """
    found: list[tuple[int, str]] = []
    for paragraph in paragraphs(text):
        if all(_BADGE.sub("", line).strip() == "" and _EXTERNAL_IMAGE.search(line) for _, line in paragraph):
            continue
        for number, line in paragraph:
            found.extend((number, match["url"]) for match in _EXTERNAL_IMAGE.finditer(line))
    return found


def raw_html(text: str) -> list[tuple[int, str]]:
    """🇺🇸 `(line, tag)` of every HTML tag or comment outside fences and inline code — none is allowed.

    Inside a fence it is code (a mermaid label may say `<br/>`); inside
    backticks it is a code span; anywhere else the site would show it as
    literal text, so it is a problem here, not on the published page.

    🇧🇷 `(linha, tag)` de toda tag ou comentário HTML fora de cerca e de código inline — nenhum é permitido.

    Dentro de cerca é código (um rótulo mermaid pode dizer `<br/>`); entre
    crases é um trecho de código; em qualquer outro lugar o site mostraria
    como texto literal, então o problema é apontado aqui, não na página.
    """
    found: list[tuple[int, str]] = []
    for number, line in outside_fences(text):
        for match in _RAW_HTML.finditer(_INLINE_CODE.sub("", line)):
            found.append((number, match[0] if match[0] == "<!--" else match[0].split()[0].rstrip("/>") + ">"))
    return found


def structure(text: str) -> list[str]:
    """🇺🇸 The skeleton two translations must share: heading levels and fence languages, in order.

    🇧🇷 O esqueleto que duas traduções precisam compartilhar: níveis de título e linguagens de cerca, em ordem.
    """
    items = [(line, f"h{level}") for level, _, line in headings(text)]
    items += [(fence.line, f"```{fence.language}") for fence in fences(text)]
    return [kind for _, kind in sorted(items)]
