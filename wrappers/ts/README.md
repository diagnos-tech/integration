# diagnos

**The diagnos vault from Node.js — find the docs, then set up the zero-knowledge SDK, CLI and REST API, step by step.**

**English** · [Português (Brasil)](README.pt-BR.md)

[![npm](https://img.shields.io/npm/v/diagnos?color=cb3837)](https://www.npmjs.com/package/diagnos)
[![Node.js ≥ 22](https://img.shields.io/badge/node-%E2%89%A5%2022-417e38)](https://nodejs.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-64748b)](https://github.com/diagnos-tech/integration/blob/main/LICENSE)

diagnos encrypts everything clinical **inside your process** before it touches the network — the vault only ever
sees ciphertext. The SDK, the command line and the REST API are written in Python and ship as one package,
[`diagnos` on PyPI](https://pypi.org/project/diagnos/), plus a signed container image. This package is the door for
Node.js developers: no dependencies, nothing runs on install, and it does exactly four things — the same four, the
same way, as `pip install diagnos`.

```sh
npx diagnos                 # what is here
npx diagnos docs dev        # https://dev.diagnos.health
npx diagnos setup api       # pull the REST API image and verify its signature
```

## Commands

| Command | Does |
|---|---|
| `diagnos docs [help\|dev\|trust] [--open] [--json]` | Lists the Help Center, Developer Central and Trust Center; with a topic, prints that URL alone (or opens it) |
| `diagnos version [--json]` | This wrapper's version, its runtime and platform, and which Python layers are installed |
| `diagnos setup sdk\|cli\|api [--yes] [--dry-run]` | Installs one layer: the SDK and the CLI with `uv`, the API as its signed image with Docker |
| `diagnos help [command]` | The overview, or one command's options |

Every other command — `diagnos login`, `diagnos patients list`, … — belongs to the full command line. Once
`diagnos setup cli` has installed it, this `diagnos` hands those commands to it unchanged, so one `diagnos` answers
everything whichever comes first on your `PATH`.

## What `setup` installs

| Target | Needs | Runs |
|---|---|---|
| `sdk` | [uv](https://docs.astral.sh/uv/) | `uv add "diagnos[sdk]>=<version>"` in the Python project around you, `uv pip install` into the active virtual environment, or `uv init` + `uv add` right here |
| `cli` | uv | `uv tool install "diagnos[cli]==<version>"` — or, if a Python `diagnos` is already installed, that one adds its own CLI where it lives |
| `api` | [Docker](https://docs.docker.com/get-started/get-docker/), optionally [cosign](https://docs.sigstore.dev/cosign/system_config/installation/) ≥ 3.1.3 | `docker pull ghcr.io/diagnos-tech/diagnos-api:<version>`, then `cosign verify` of the digest that was pulled, then prints a hardened `docker run` by that digest |

`<version>` is this package's own version: `diagnos@0.1.0` from npm sets up `diagnos==0.1.0` from PyPI and the
`0.1.0` image. They are released together.

## Safe by design

- **Shows before it runs.** Every command `setup` will run is printed first and confirmed once, defaulting to *no*.
  `--yes` skips the question, `--dry-run` runs nothing. Without a terminal and without `--yes`, nothing runs.
- **Never installs a tool.** A missing `uv` or Docker ends with its official install page and exit code `69` —
  never a downloaded installer, never `curl | sh`.
- **No shell, no surprises on `PATH`.** Programs run from an argument list, resolved once to an absolute path;
  relative `PATH` entries are ignored, and on Windows only `.exe` files are run.
- **Verifies what it pulls.** The API image is verified *by the digest Docker pulled*, against one signer: the
  integration repository's `release.yml`, run by the push of this version's tag, through GitHub's OIDC issuer. An
  image whose signature fails is removed on the spot. Without cosign it says *NOT verified*, loudly.
- **Escapes what it did not write.** Paths and other outside text are printed with control characters escaped, so
  nothing can recolor or rewrite the plan you approve.
- **Nothing in the background.** No install scripts, no telemetry, no network access of its own: the only programs
  it talks to are the ones it shows you.

## For scripts

`--json` prints the same shapes as the Python base. `diagnos docs --json`:

```json
{
  "help": { "name": "Help Center", "url": "https://docs.diagnos.health" },
  "dev": { "name": "Developer Central", "url": "https://dev.diagnos.health" },
  "trust": { "name": "Trust Center", "url": "https://trust.diagnos.health" }
}
```

`diagnos version --json` gives `diagnos`, `node`, `implementation`, `executable`, `platform`, `extras` (the Python
base's own `{extra: installed}`, empty when there is none) and `layers` (which Python `diagnos` answered, or `null`).
Text output is bilingual (`English · Português`) and honors `NO_COLOR`.

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | A step failed, or the confirmation was declined |
| `2` | Usage error (including "no terminal to confirm on") |
| `69` | Something this needs — `uv`, Docker — is not installed |

The same command line is importable: `import { main } from "diagnos"; process.exitCode = await main(["docs", "--json"]);`.

## Learn more

- **Help Center** — <https://docs.diagnos.health>
- **Developer Central** — <https://dev.diagnos.health>
- **Trust Center** — <https://trust.diagnos.health>
- **Source, issues and changelog** — <https://github.com/diagnos-tech/integration> (this package lives in
  `wrappers/ts`, and implements [`wrappers/contract.json`](https://github.com/diagnos-tech/integration/blob/develop/wrappers/contract.json))

Licensed under [Apache-2.0](https://github.com/diagnos-tech/integration/blob/main/LICENSE). Report a vulnerability
privately through [GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new).
