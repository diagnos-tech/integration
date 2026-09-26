# Documentation

**English** · [Português (Brasil)](README.pt-BR.md)

This repository is the single source of the diagnos developer documentation. The website publishes it at
`/dev/docs`, reading this repository at a pinned commit; GitHub renders the very same files. This page is for people
who write or change the docs: where everything lives, the rules every page follows, and what `make docs-check` proves
before a change can merge.

## Layout

```text
README.md                     the overview page (the site's root)
apps/sdk/README.md            package home pages — also the PyPI descriptions
apps/cli/README.md
apps/api/README.md
apps/api/deploy/**/README.md  deployment: Docker Compose, Kubernetes, OpenBao auto-unseal
docs/
├── README.md                 this page
├── site.json                 navigation, page ids and SEO descriptions — written by hand
├── guides/                   quickstart, concepts, sessions, patients, … — the hand-written guides
├── reference/                openapi.json, cli.json, sdk.json — GENERATED from the code, never edited
├── PROTOCOL.md               the normative wire contract
└── COMPATIBILITY.md          what works against today's vault
scripts/docs/                 the generators and the checks behind `make docs` and `make docs-check`
```

## Writing a page

- **Two files, one page.** Every page is `NAME.md` (English) next to `NAME.pt-BR.md` (Brazilian Portuguese), with a
  language switcher right under the H1. Both must share the same skeleton — the same heading levels and the same code
  fences, in the same order — and `make docs-check` compares them.
- **The first `# H1` is the title.** No YAML frontmatter: GitHub would render it as a table on top of the page.
  Whatever the site needs besides Markdown lives in [`site.json`](site.json).
- **Every fact lives in one place.** Explain a thing once and link to it; package READMEs are home pages that point
  into the guides, not copies of them. Commands, routes and classes are listed in the generated reference, never
  typed by hand into a table.
- **Links are relative** (`[Sessions](guides/sessions.md#auto-unseal-with-openbao)`): the site turns a link to a page
  of the manifest into a link to that page, and anything else into a GitHub link at the pinned commit. Package
  READMEs link to files outside their package with absolute GitHub URLs, because PyPI cannot resolve relative ones.
  To point at a reference section, link its JSON file (`reference/sdk.json`).
- **Alerts and diagrams**: `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]` and `> [!CAUTION]` become
  callouts, and ```` ```mermaid ```` fences become diagrams — on GitHub and on the site. Use them where they clarify,
  not to decorate.
- **The voice** is the repository's: direct, precise, and always saying *why* — the threat, the cost, the protocol
  rule. [CONTRIBUTING.md](../CONTRIBUTING.md) has the rest of the conventions.

### Adding a page to the site

A Markdown file is published only once `site.json` lists it, inside a navigation group:

```json
{
  "id": "sdk/patients",
  "source": "docs/guides/patients.md",
  "description": {
    "en": "Create, read, update, archive and delete encrypted patient records with the diagnos SDK…",
    "pt-br": "Crie, leia, atualize, arquive e apague registros de paciente cifrados com o SDK diagnos…"
  }
}
```

- `id` is the page's URL (`/<lang>/dev/docs/<id>/`): lowercase letters, digits and `-`, in `/`-separated segments,
  unique across the manifest. `overview` is the root page and is required.
- `source` is the English file; its `.pt-BR.md` twin is the Portuguese page.
- `description` is search-engine copy — at most 160 characters in each language — not prose from the page.
- `title` is only for a file whose H1 cannot serve as a menu title (the root README's centered HTML heading).
- Renaming an `id` breaks every link to it: add `{"from": "old/id", "to": "new/id"}` to `redirects`.
- A page with `"reference": "openapi" | "cli" | "sdk"` instead of a `source` is a generated section; the site expands
  it into one page per route, command or class.

## Runnable examples

Every ```` ```python ```` block of every page in `site.json` — both languages — runs in CI. That is the convention,
and the reason an example here can be trusted:

- The blocks of a page run top to bottom, **in one namespace**, like a notebook: a later block may use `vault` or
  `patient` from an earlier one. Each page starts from a fresh sandbox.
- ```` ```python no-run ```` opts one block out — a fragment, a signature, or code that needs a real OpenBao or a
  running API. Any other language never runs.
- **The sandbox is the real SDK against an in-memory vault.** `Diagnos()` parses a sandbox token, enrolls with a real
  hybrid key pair, signs every request and seals every record and file in the Rust enclave; only the network is
  replaced, by the SDK's own test double of the vault and object storage
  (`apps/sdk/tests/resources/vault_double.py`). Every enrollment is approved at once with the groups `sg_oncology`
  and `sg_radiology`, and the working directory holds `scans/IM-0001.dcm`, `scans/IM-0002.dcm`, `photo.jpg` and
  `report.pdf`.
- Output is captured, and shown only when a block fails, at the Markdown line that raised.

Shell blocks do not run, but every `diagnos …` line in them is parsed against the CLI: an unknown command or flag
fails the check.

## Reference pages

The three files in `docs/reference/` are generated from the code by `make docs`, and committed. To change what the
reference says, change the code:

| File | Generated from | Text comes from |
|---|---|---|
| `openapi.json` | the FastAPI app, `app.openapi()` | route `summary`/`description` and parameter descriptions, written `🇺🇸 … 🇧🇷 …` |
| `cli.json` | the `typer` command tree of `diagnos` | `help=` texts written `English · Português`; examples from each command's epilog (`diagnos_cli.examples`) |
| `sdk.json` | `diagnos.__all__`, read with `inspect` | docstrings, with the 🇺🇸/🇧🇷 paragraphs; fields documented by a string literal right under them |

The 🇺🇸/🇧🇷 split follows one rule, shared with the site (`scripts/docs/bilingual.py`): from 🇺🇸 to 🇧🇷 is English,
from 🇧🇷 on is Portuguese; text without markers is published untranslated, which the check refuses.
`generatedFrom.commit` records the commit a reference was last regenerated on top of; it changes only when the
content does.

## The checks

```sh
make docs         # regenerate docs/reference/*.json
make docs-check   # everything below; part of `make check`, so CI runs it on every pull request
```

`make docs-check` fails when:

- a generated file differs from what `make docs` would write;
- `site.json` breaks the contract — an id outside the grammar or repeated, a missing source or `.pt-BR.md` twin, a
  description over 160 characters or missing a language;
- a page and its twin do not share a skeleton;
- a relative link, an anchor, or an absolute link into this repository does not resolve;
- a runnable example fails, or a `diagnos …` line uses a command or flag that does not exist;
- `diagnos … --help` disagrees with `cli.json`, in either direction;
- any generated text is untranslated.

`make lint` separately checks that *every* Markdown file of the repository has its twin, its language switcher and no
dead relative link (`scripts/check_docs.py`).
