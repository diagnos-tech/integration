"""The documentation pipeline: generate the reference JSON from the code, then prove the docs still hold.

The site at `/dev/docs` reads three things from this repository
(`docs/README.md` has the whole picture): `docs/site.json` (navigation and
SEO copy, written by hand), the Markdown guides, and `docs/reference/*.json`
— generated here from the code so the site never types an endpoint, a
command or a class name.

- `generate` — `make docs`: runs `openapi`, `cli` and `sdk` and writes the JSON.
- `check` — `make docs-check`: stale JSON, the manifest, links and anchors,
  runnable snippets, `diagnos … --help` against `cli.json`.
- `l10n` — the `{"en", "pt-br"}` pair the generated JSON carries: the code is
  English-only, so both locales hold the same text.
"""
