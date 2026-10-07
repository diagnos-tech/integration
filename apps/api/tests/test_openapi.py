"""🇺🇸 `/openapi.json` matches `README.md`'s prefix table, and every operation carries both language flags.

Every route, parameter and schema is in the generated reference
(`docs/reference/openapi.json`, kept fresh by `make docs-check`). What stays
hand-written is the short table of prefixes in `README.md` — what a human
skims first — so nothing stops it from drifting out of sync with the routers
as they grow. This file parses that table and checks it both ways: every
prefix it lists still has a real route under it, and every route FastAPI
serves falls under a listed prefix. Separately, every operation FastAPI
actually generated still carries a 🇺🇸/🇧🇷 pair somewhere in its
`summary`/`description` (`CONTRIBUTING.md`'s bilingual-docstring rule, applied
to the one artifact an external caller reads instead of the source).

🇧🇷 `/openapi.json` bate com a tabela de prefixos do `README.md`, e toda
operação carrega as duas bandeiras de idioma.

Toda rota, parâmetro e schema está na referência gerada
(`docs/reference/openapi.json`, mantida em dia pelo `make docs-check`). O que
continua escrito à mão é a tabela curta de prefixos do `README.md` — o que
uma pessoa lê primeiro — então nada impede que ela desalinhe dos roteadores
conforme crescem. Este arquivo interpreta essa tabela e confere nos dois
sentidos: todo prefixo listado ainda tem uma rota real embaixo, e toda rota
que o FastAPI serve cai sob um prefixo listado. Separadamente, toda operação
que o FastAPI de fato gerou ainda carrega um par 🇺🇸/🇧🇷 em algum lugar do
`summary`/`description` (a regra de docstring bilíngue do `CONTRIBUTING.md`,
aplicada ao único artefato que quem chama de fora lê no lugar do
código-fonte).
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

_README = Path(__file__).parent.parent / "README.md"

# 🇺🇸 A README row looks like `| `/v1/drives/{sg}` | files and folders … |` —
# only the first backtick-quoted cell (the prefix) matters here; "What it
# serves" is prose, not part of the route contract.
# 🇧🇷 Uma linha do README parece `| `/v1/drives/{sg}` | arquivos e pastas … |`
# — só a primeira célula entre crases (o prefixo) importa aqui; "What it
# serves" é prosa, não parte do contrato de rota.
_ROW = re.compile(r"^\| `(/[^`]*)` \|", re.MULTILINE)

_METHODS = ("get", "post", "put", "delete", "patch")


def _normalize(path: str) -> str:
    """🇺🇸 Collapses any `{param}` segment to `{}` so `{sg}` (README) matches whatever the real route names it.

    🇧🇷 Colapsa todo segmento `{param}` para `{}`, para `{sg}` (README) bater com o nome que a rota real der.
    """
    return re.sub(r"\{[^}]+\}", "{}", path)


def _readme_prefixes() -> list[str]:
    """🇺🇸 Every prefix in `README.md`'s table, normalized, in file order.

    🇧🇷 Todo prefixo da tabela do `README.md`, normalizado, na ordem do arquivo.
    """
    return [_normalize(prefix) for prefix in _ROW.findall(_README.read_text(encoding="utf-8"))]


def _served_paths(client: TestClient) -> set[str]:
    """🇺🇸 Every path FastAPI serves an operation on, normalized. 🇧🇷 Todo path com operação servida, normalizado."""
    spec = client.get("/openapi.json").json()
    return {_normalize(path) for path, item in spec["paths"].items() if any(method in item for method in _METHODS)}


def _is_under(path: str, prefix: str) -> bool:
    """🇺🇸 `path` is `prefix` itself or a route below it. 🇧🇷 `path` é o próprio `prefix` ou uma rota abaixo dele."""
    return path == prefix or path.startswith(prefix + "/")


def test_readme_lists_the_documented_prefixes(client: TestClient) -> None:
    """🇺🇸 Sanity check on the parser itself: the table has to have found real rows, not zero from a bad regex.

    🇧🇷 Checagem de sanidade do próprio parser: a tabela precisa ter achado linhas de verdade, não zero por regex ruim.
    """
    assert len(_readme_prefixes()) >= 5


def test_every_readme_prefix_has_a_route_and_every_route_a_readme_prefix(client: TestClient) -> None:
    """🇺🇸 The README's table and the routers agree both ways: no prefix without a route, no route without a prefix.

    A prefix with nothing under it means the README documents routes that
    no longer exist; a served path under no prefix means a router was added
    without a row in the table an integrator reads first — either way,
    exactly the kind of drift a test should catch instead of a human noticing
    months later.

    🇧🇷 A tabela do README e os roteadores concordam nos dois sentidos: nenhum prefixo sem rota, nenhuma rota sem
    prefixo.

    Um prefixo sem nada embaixo significa que o README documenta rotas que
    não existem mais; um path servido fora de todo prefixo significa que um
    roteador foi adicionado sem uma linha na tabela que um integrador lê
    primeiro — de qualquer jeito, exatamente o tipo de desalinho que um
    teste deveria pegar em vez de uma pessoa notar meses depois.
    """
    prefixes, served = _readme_prefixes(), _served_paths(client)

    for prefix in prefixes:
        assert any(_is_under(path, prefix) for path in served), f"{prefix} is documented but nothing is served under it"
    for path in sorted(served):
        assert any(_is_under(path, prefix) for prefix in prefixes), f"{path} is served but under no documented prefix"


def test_every_operation_has_both_language_flags_in_summary_or_description(client: TestClient) -> None:
    """🇺🇸 Every operation's `summary`+`description`, combined, carries both 🇺🇸 and 🇧🇷 — the bilingual-docstring rule.

    A `summary` alone is sometimes just `"List patients · Lista pacientes"`
    with no flag emoji at all; the flags live in `description` instead. What
    matters to an integrator reading `/docs` is that the pair is findable
    *somewhere* on the operation, not which of the two fields carries it.

    🇧🇷 O `summary`+`description` de toda operação, combinados, carrega tanto
    🇺🇸 quanto 🇧🇷 — a regra de docstring bilíngue.

    Um `summary` sozinho às vezes é só `"List patients · Lista pacientes"`
    sem emoji de bandeira nenhum; as bandeiras moram no `description` no
    lugar. O que importa para um integrador lendo `/docs` é que o par seja
    encontrável *em algum lugar* da operação, não qual dos dois campos
    carrega.
    """
    spec = client.get("/openapi.json").json()
    checked = 0
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in _METHODS:
                continue
            combined = operation.get("summary", "") + operation.get("description", "")
            assert "🇺🇸" in combined, f"{method.upper()} {path} has no English flag in summary/description"
            assert "🇧🇷" in combined, f"{method.upper()} {path} has no Portuguese flag in summary/description"
            checked += 1

    # 🇺🇸 Guards the loop itself: an empty `spec["paths"]` would make every
    # assertion above vacuously true.
    # 🇧🇷 Protege o próprio laço: um `spec["paths"]` vazio faria toda
    # asserção acima ser verdadeira por vacuidade.
    assert checked >= 20
