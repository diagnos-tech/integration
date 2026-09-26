# diagnos-cli

**English** · [Português (Brasil)](README.pt-BR.md)

The `diagnos` command line — the zero-knowledge diagnos vault, from your terminal, built on the
[`diagnos`](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.md) SDK. Every byte of
cryptography, signing and retry logic lives in the SDK; this package only parses arguments and renders what the SDK
returns — tables for people, JSON for scripts, stable exit codes for both.

> [!NOTE]
> **Not on PyPI yet.** `pipx install diagnos-cli` below is the intended, permanent install command — but until the
> first release, install from source instead (building the SDK needs a [Rust toolchain](https://rustup.rs/); `cli`
> depends on the not-yet-published `diagnos` SDK, so both come from git in one command):
> ```sh
> pipx install "diagnos-cli @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/cli" \
>   --preinstall "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"
> ```
> Coming from `imgexam-cli`? Versions restart at `0.1.0` under the new name — read
> [MIGRATING.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.md) before upgrading.

## Install

```sh
pipx install diagnos-cli
pipx install "diagnos-cli[openbao]"   # with OpenBao auto-unseal, for cron jobs and servers
export DIAGNOS_API_TOKEN="apikey-…"   # issued by a workspace admin
```

`--token` on any command overrides the environment for that one invocation, and is never echoed — not in `--help`,
not in output, not in `--json`.

## A first run

```sh
diagnos login                                      # prints a link and a code; an admin approves
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology --exam EXAM_ID scans/*.dcm
diagnos --json exams get EXAM_ID | jq .record.report_html
```

Each invocation is its own process, and **the CLI never writes a session to disk**: without OpenBao, the next
command enrolls again with a new link and code. That is deliberate — a script that runs unattended configures
OpenBao auto-unseal instead, as the CLI guide shows.

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
uv run --package diagnos-cli pytest apps/cli/tests -q
uv run ruff check apps/cli && uv run ruff format --check apps/cli
uv run mypy apps/cli/src
```

A command's examples live next to it, in its `epilog` (`diagnos_cli.examples`): they show at the bottom of `--help`
and in the generated reference, and `make docs-check` fails if the two ever disagree. See
[CONTRIBUTING.md](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.md) for the bilingual-docstring
rule and the "`cli` imports only `diagnos`" boundary.
