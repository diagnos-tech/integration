# Wrappers

**English** · [Português (Brasil)](README.pt-BR.md)

The diagnos integration is written in Python — the SDK, the command line and the REST API all ship in one package,
[`diagnos`](py/README.md). A *wrapper* is the small, dependency-free program a developer meets first, in the
language they already use: it explains where things are and installs the rest. Every wrapper does exactly four
things, the same way, so the first five minutes feel identical whether you start from `pip`, `npm` or `go`.

| Wrapper | Package | Status |
|---|---|---|
| [`py/`](py/README.md) | `pip install diagnos` — the base of the Python package itself (`src/diagnos/_wrapper`) | ✅ |
| [`ts/`](ts/README.md) | `npx diagnos` — TypeScript for Node.js, on npm as [`diagnos`](https://www.npmjs.com/package/diagnos); sets up the Python layers, most often the API's container | ✅ |
| `go/`, … | `go run …` | planned |

## The contract

[`contract.json`](contract.json) is the machine-readable source of truth: commands, options, links, setup targets
and exit codes. A wrapper ships a conformance test against it — the Python one is
[`py/tests/test_contract.py`](py/tests/test_contract.py), the TypeScript one
[`ts/test/contract.test.ts`](ts/test/contract.test.ts).

| Command | Does |
|---|---|
| `diagnos docs [help\|dev\|trust] [--open] [--json]` | Lists the Help Center, Developer Central and Trust Center; with a topic, prints that URL alone (or opens it) |
| `diagnos version [--json]` | The wrapper's version, its runtime and platform, and which Python layers are installed |
| `diagnos setup sdk\|cli\|api [--yes] [--dry-run]` | Installs one layer: the SDK and the CLI with `uv`, the API as its signed image with Docker |
| `diagnos help [command]` | The overview, or one command's options |

Rules every wrapper keeps:

- **Shows before it runs.** Every command `setup` will run is printed first and confirmed once, defaulting to
  *no*; `--yes` skips the question, `--dry-run` runs nothing. Without a terminal and without `--yes`, nothing runs
  and the exit code is `2`.
- **Never installs a tool.** A missing `uv` or Docker ends with its official install page and exit code `69` —
  never a downloaded installer, never `curl | sh`.
- **No shell, no surprises on `PATH`.** Programs run from an argv list, resolved once to an absolute path; relative
  `PATH` entries are ignored.
- **Verifies what it pulls.** `setup api` reads the digest Docker pulled, verifies that digest with `cosign`
  (≥ 3.1.3) against the `signer` in the contract — the release workflow at this version's tag, run by a `push` — and
  prints the `docker run` by digest. Without cosign it says *NOT verified*, loudly.
- **Escapes what it did not write.** Paths and other outside text are printed with control characters escaped, so
  nothing can recolor or rewrite the plan a person approves; every version it writes into a command is pinned.
- **Same output.** `--json` prints exactly the shapes the Python base prints; text output is bilingual
  (`English · Português`) and honors `NO_COLOR`.

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | A step failed, or the confirmation was declined |
| `2` | Usage error (including "no terminal to confirm on") |
| `69` | Something this needs — `uv`, Docker, an extra — is not installed |
