# diagnos · command line

**English** · [Português (Brasil)](README.pt-BR.md)

The `diagnos` command line — the zero-knowledge diagnos vault, from your terminal, built on the
[`diagnos`](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.md) SDK. Every byte of
cryptography, signing and retry logic lives in the SDK; this package only parses arguments and renders what the SDK
returns — tables for people, JSON for scripts, stable exit codes for both. It is the `cli` extra of the one
`diagnos` package; its code lives in `src/diagnos/cli`.

> [!NOTE]
> **Until `0.1.0` is on PyPI**, install from the repository (building the SDK needs a
> [Rust toolchain](https://rustup.rs/)):
> ```sh
> uv tool install "diagnos[cli] @ git+https://github.com/diagnos-tech/integration@develop"
> ```
> Coming from `imgexam-cli` or `diagnos-cli`? Read
> [MIGRATING.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.md) before upgrading.

## Install

```sh
uv tool install "diagnos[cli]"            # or: pipx install "diagnos[cli]"
uv tool install "diagnos[cli,openbao]"    # with OpenBao auto-unseal, for cron jobs and servers
export DIAGNOS_API_TOKEN="apikey-…"       # issued by a workspace admin
```

Already have the base (`pip install diagnos`)? `diagnos setup cli` adds the rest to that same `diagnos`. Without
Python, the image works too: `docker run --rm -e DIAGNOS_API_TOKEN ghcr.io/diagnos-tech/diagnos patients list`.

`--token` on any command overrides the environment for that one invocation, and is never echoed — not in `--help`,
not in output, not in `--json`.

## A first run

```sh
diagnos login                                      # prints a link and a code; an admin approves
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology --exam EXAM_ID scans/*.dcm
diagnos --json exams get EXAM_ID | jq .record.report_html
diagnos logout                                     # revokes the session and wipes its keys
```

`login` keeps that session for the commands that follow — no new link, no new code — until `diagnos logout`. It
lives in one background process, the *session agent*, in the SDK's locked memory: **the CLI never writes a session
to disk**. Without `login`, each command enrolls on its own and its session dies with it — a script that runs
unattended configures OpenBao auto-unseal instead, as the CLI guide shows.

## Guides

| | |
|---|---|
| [CLI guide](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/cli.md) | every command with real examples, JSON output, scripting and cron |
| [CLI reference](https://github.com/diagnos-tech/integration/blob/develop/docs/reference/cli.json) | every command and option, generated from the code — also `diagnos <command> --help` |
| [Authentication](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/authentication.md) | the token, the enrollment panel, the approval |
| [Sessions](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/sessions.md#auto-unseal-with-openbao) | OpenBao auto-unseal, and what it trades |
| [Errors](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/errors.md#every-exception) | the exit code of every failure |
| [Configuration](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/configuration.md) | every environment variable |

Known limits and the questions still open on the vault side:
[Compatibility with the vault](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.md).

## Development

```sh
make sync
uv run pytest apps/cli/tests -q
uv run ruff check src/diagnos/cli apps/cli && uv run ruff format --check src/diagnos/cli apps/cli
uv run mypy src
```

A command's examples live next to it, in its `epilog` (`diagnos.cli.examples`): they show at the bottom of `--help`
and in the generated reference, and `make docs-check` fails if the two ever disagree. See
[CONTRIBUTING.md](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.md) for the bilingual-docstring
rule and the "`diagnos.cli` imports only `diagnos`" boundary.
