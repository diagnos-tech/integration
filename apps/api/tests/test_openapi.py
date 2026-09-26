"""🇺🇸 `/openapi.json` matches `README.md`'s route table, and every operation carries both language flags.

An integrator's first stop is `/docs`/`/openapi.json` (`README.md`: "Full
request/response schemas, generated from the code"), not the README table
itself — but the table is what a human skims first, and it is hand-written,
so nothing stops it from drifting out of sync with the routers as they grow.
This file parses `README.md`'s own table and checks every row it lists is
still a real route with that method, and separately checks every operation
FastAPI actually generated still carries a 🇺🇸/🇧🇷 pair somewhere in its
`summary`/`description` (`CONVENTIONS.md`'s bilingual-docstring rule, applied
to the one artifact an external caller reads instead of the source).

🇧🇷 `/openapi.json` bate com a tabela de rotas do `README.md`, e toda
operação carrega as duas bandeiras de idioma.

A primeira parada de um integrador é `/docs`/`/openapi.json` (`README.md`:
"Full request/response schemas, generated from the code"), não a própria
tabela do README — mas a tabela é o que uma pessoa lê primeiro, e é escrita à
mão, então nada impede que ela desalinhe dos roteadores conforme crescem.
Este arquivo interpreta a própria tabela do `README.md` e confere que toda
linha listada ainda é uma rota real com aquele método, e separadamente
confere que toda operação que o FastAPI de fato gerou ainda carrega um par
🇺🇸/🇧🇷 em algum lugar do `summary`/`description` (a regra de docstring
bilíngue do `CONVENTIONS.md`, aplicada ao único artefato que quem chama de
fora lê no lugar do código-fonte).
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

_README = Path(__file__).parent.parent / "README.md"

# 🇺🇸 A README row looks like `| `GET` | `/v1/patients/{id}` | ... | ✅ works
# today |` — only the first two backtick-quoted cells (method, path) matter
# here; "What it does"/"Status" are prose, not part of the route contract.
# 🇧🇷 Uma linha do README parece `| `GET` | `/v1/patients/{id}` | ... | ✅
# works today |` — só as duas primeiras células entre crases (método, path)
# importam aqui; "What it does"/"Status" são prosa, não parte do contrato de rota.
_ROW = re.compile(r"^\| `(GET|POST|PUT|DELETE|PATCH)` \| `([^`]+)` \|", re.MULTILINE)

_METHODS = ("get", "post", "put", "delete", "patch")


def _normalize(path: str) -> str:
    """🇺🇸 Collapses any `{param}` segment to `{}` so `{id}` (README) matches `{patient_id}` (the real route).

    🇧🇷 Colapsa todo segmento `{param}` para `{}`, para `{id}` (README) bater com `{patient_id}` (a rota real).
    """
    return re.sub(r"\{[^}]+\}", "{}", path)


def _readme_routes() -> list[tuple[str, str]]:
    """🇺🇸 Every `(METHOD, path)` row in `README.md`'s route table, in file order.

    🇧🇷 Toda linha `(METODO, path)` da tabela de rotas do `README.md`, na ordem do arquivo.
    """
    return [(method, path) for method, path in _ROW.findall(_README.read_text())]


def test_readme_lists_at_least_the_documented_routes(client: TestClient) -> None:
    """🇺🇸 Sanity check on the parser itself: the table has to have found real rows, not zero from a bad regex.

    🇧🇷 Checagem de sanidade do próprio parser: a tabela precisa ter achado linhas de verdade, não zero por regex ruim.
    """
    assert len(_readme_routes()) >= 20


def test_every_readme_route_exists_in_openapi_with_the_same_method(client: TestClient) -> None:
    """🇺🇸 Every `(method, path)` the README's table promises is a real operation FastAPI actually serves.

    A row here with no matching operation means either the README documents
    a route that no longer exists, or a router was renamed/removed without
    updating the table an integrator reads first — either way, exactly the
    kind of drift a generated schema should catch instead of a human
    noticing months later.

    🇧🇷 Todo `(método, path)` que a tabela do README promete é uma operação
    real que o FastAPI de fato serve.

    Uma linha aqui sem operação correspondente significa que o README
    documenta uma rota que não existe mais, ou que um roteador foi
    renomeado/removido sem atualizar a tabela que um integrador lê primeiro
    — de qualquer jeito, exatamente o tipo de desalinho que um schema gerado
    deveria pegar em vez de uma pessoa notar meses depois.
    """
    spec = client.get("/openapi.json").json()
    actual = {
        (method.upper(), _normalize(path))
        for path, item in spec["paths"].items()
        for method in item
        if method in _METHODS
    }

    for doc_method, doc_path in _readme_routes():
        assert (doc_method, _normalize(doc_path)) in actual, f"{doc_method} {doc_path} is documented but not served"


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
