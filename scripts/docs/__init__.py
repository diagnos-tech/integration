"""🇺🇸 The documentation pipeline: generate the reference JSON from the code, then prove the docs still hold.

The site at `/dev/docs` reads three things from this repository
(`docs/README.md` has the whole picture): `docs/site.json` (navigation and
SEO copy, written by hand), the Markdown guides, and `docs/reference/*.json`
— generated here from the code so the site never types an endpoint, a
command or a class name.

- `generate` — `make docs`: runs `openapi`, `cli` and `sdk` and writes the JSON.
- `check` — `make docs-check`: stale JSON, the manifest, links and anchors,
  runnable snippets, `diagnos … --help` against `cli.json`.
- `bilingual` — the one rule that splits 🇺🇸/🇧🇷 text, shared with the site.

🇧🇷 O pipeline de documentação: gera o JSON de referência a partir do código e prova que a doc continua de pé.

O site em `/dev/docs` lê três coisas deste repositório (`docs/README.pt-BR.md`
tem o quadro completo): `docs/site.json` (navegação e copy de SEO, escrito à
mão), os guias em Markdown e `docs/reference/*.json` — gerados aqui a partir
do código para o site nunca digitar um endpoint, comando ou nome de classe.

- `generate` — `make docs`: roda `openapi`, `cli` e `sdk` e grava os JSON.
- `check` — `make docs-check`: JSON velho, o manifesto, links e âncoras,
  snippets executáveis, `diagnos … --help` contra o `cli.json`.
- `bilingual` — a regra única que divide texto 🇺🇸/🇧🇷, compartilhada com o site.
"""
