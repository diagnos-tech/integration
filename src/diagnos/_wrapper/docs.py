"""🇺🇸 `diagnos docs` — where to read more: the Help Center, Developer Central and the Trust Center.

The bare command lists all three. With a topic it prints that one URL alone,
so it composes (`open "$(diagnos docs dev)"`); `--open` hands it to the
browser instead.

🇧🇷 `diagnos docs` — onde ler mais: a Central de Ajuda, a Developer Central e o Trust Center.

O comando sozinho lista os três. Com um tópico imprime só aquela URL, para
compor (`open "$(diagnos docs dev)"`); `--open` a entrega ao navegador.
"""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .exit_codes import EXIT_OK, EXIT_USAGE
from .output import Output, table


class Topic(StrEnum):
    """🇺🇸 The three documentation sites, by the short name `diagnos docs <topic>` takes.

    🇧🇷 Os três sites de documentação, pelo nome curto que o `diagnos docs <tópico>` recebe.
    """

    HELP = "help"
    DEV = "dev"
    TRUST = "trust"


@dataclass(frozen=True)
class Link:
    """🇺🇸 One documentation site: its topic id, its name, its URL and what is there.

    🇧🇷 Um site de documentação: o id do tópico, o nome, a URL e o que há lá.
    """

    topic: Topic
    name: str
    url: str
    about: str


LINKS: Final = (
    Link(
        Topic.HELP,
        "Help Center",
        "https://docs.diagnos.health",
        "Guides and answers for every diagnos product · Guias e respostas de todo produto diagnos",
    ),
    Link(
        Topic.DEV,
        "Developer Central",
        "https://dev.diagnos.health",
        "SDK, CLI and REST API: guides and reference · SDK, CLI e API REST: guias e referência",
    ),
    Link(
        Topic.TRUST,
        "Trust Center",
        "https://trust.diagnos.health",
        "Security, privacy and compliance · Segurança, privacidade e conformidade",
    ),
)
TOPICS: Final = tuple(topic.value for topic in Topic)


def docs(topic: str | None, *, open_browser: bool, out: Output) -> int:
    """🇺🇸 Lists the three sites, prints one URL, or opens it; returns the exit code.

    🇧🇷 Lista os três sites, imprime uma URL ou a abre; devolve o código de saída.
    """
    chosen = [link for link in LINKS if topic in (None, link.topic)]
    if open_browser:
        if topic is None:
            out.error(f"--open needs a topic · --open precisa de um tópico: {', '.join(TOPICS)}")
            return EXIT_USAGE
        if not webbrowser.open(chosen[0].url):
            out.error(f"No browser here · Sem navegador aqui: {chosen[0].url}")
        return EXIT_OK
    if out.json_output:
        out.data({link.topic: {"name": link.name, "url": link.url} for link in chosen})
    elif topic is not None:
        out.line(chosen[0].url)
    else:
        for row in table([(link.name, link.url, link.about) for link in chosen], indent=0):
            out.line(row)
    return EXIT_OK
