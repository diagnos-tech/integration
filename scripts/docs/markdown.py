"""🇺🇸 Just enough Markdown for the checks: fenced blocks, headings and GitHub's anchor slugs.

Not a Markdown parser — the site has a real one. These are the three
facts the checks need, read the way GitHub reads them (the repository has
to stay readable there without the site): a fence opens with three or
more backticks or tildes and closes with the same character, at least as
long; a heading is `#`… outside a fence; an anchor is GitHub's slug of the
heading text, with `-1`, `-2`… on repeats.

🇧🇷 Só o Markdown que as checagens precisam: blocos cercados, títulos e os slugs de âncora do GitHub.

Não é um parser de Markdown — o site tem um de verdade. São os três fatos
que as checagens precisam, lidos do jeito que o GitHub os lê (o repositório
precisa continuar legível lá sem o site): uma cerca abre com três ou mais
crases ou tils e fecha com o mesmo caractere, no mínimo do mesmo tamanho;
um título é `#`… fora de cerca; uma âncora é o slug do GitHub para o texto
do título, com `-1`, `-2`… nas repetições.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_OPEN = re.compile(r"^(?P<indent> *)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_HEADING = re.compile(r"^(?P<marks>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")
_ANCHOR_ID = re.compile(r"""<a\s+[^>]*(?:id|name)="([^"]+)\"""")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
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
    """🇺🇸 Every anchor a link may target in `text`: heading slugs (deduplicated GitHub's way) and HTML ids.

    🇧🇷 Toda âncora que um link pode mirar em `text`: slugs de título (desduplicados como o GitHub) e ids HTML.
    """
    seen: dict[str, int] = {}
    found: set[str] = set()
    for _, title, _ in headings(text):
        base = slug(title)
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    found.update(match.lower() for match in _ANCHOR_ID.findall(text))
    return found


def structure(text: str) -> list[str]:
    """🇺🇸 The skeleton two translations must share: heading levels and fence languages, in order.

    🇧🇷 O esqueleto que duas traduções precisam compartilhar: níveis de título e linguagens de cerca, em ordem.
    """
    items = [(line, f"h{level}") for level, _, line in headings(text)]
    items += [(fence.line, f"```{fence.language}") for fence in fences(text)]
    return [kind for _, kind in sorted(items)]
