# diagnos · command line

**English** · [Português (Brasil)](README.pt-BR.md)

The `diagnos` command line — the zero-knowledge diagnos vault, from your terminal, built on the
[`diagnos`](https://github.com/diagnos-tech/integration/blob/main/apps/sdk/README.md) SDK. Every byte of
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
> [MIGRATING.md](https://github.com/diagnos-tech/integration/blob/main/MIGRATING.md) before upgrading.

## Install

```sh
uv tool install "diagnos[cli]"            # or: pipx install "diagnos[cli]"
uv tool install "diagnos[cli,openbao]"    # with OpenBao, where a server keeps the token
```

Already have the base (`pip install diagnos`)? `diagnos setup cli` adds the rest to that same `diagnos`. Without
Python, the image works too: `docker run --rm -e DIAGNOS_TOKEN ghcr.io/diagnos-tech/diagnos patients list`.

`--token` on any command overrides every other source for that one invocation, and is never echoed — not in
`--help`, not in output, not in `--json`. Prefer `diagnos login`: a token on the command line ends up in shell
history.

## A first run

```sh
diagnos login                                      # paste the token (dgn_sk1_…) once — hidden input
diagnos whoami                                     # which token, from where, and its groups
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology --exam EXAM_ID scans/*.dcm
diagnos --json exams get EXAM_ID | jq .record.report_html
diagnos logout                                     # forgets the stored token
```

`login` checks the token's CRC before any network call, proves it against the vault, and keeps it in the system
keyring — only one that encrypts at rest — else in OpenBao (`OPENBAO_ADDR`), else refuses and says why. **The CLI
never writes the token to a file.** Every command then opens its own session with one signed request: no link, no
code, no approval. In CI and containers, set `DIAGNOS_TOKEN` instead; it wins over the stored token. The deprecated
`apikey-` token still enrolls with an admin's approval — `diagnos session start` approves once and keeps that session
in a background agent.

## Guides

| | |
|---|---|
| [CLI guide](https://github.com/diagnos-tech/integration/blob/main/docs/guides/cli.md) | every command with real examples, JSON output, scripting and cron |
| [CLI reference](https://github.com/diagnos-tech/integration/blob/main/docs/reference/cli.json) | every command and option, generated from the code — also `diagnos <command> --help` |
| [Authentication](https://github.com/diagnos-tech/integration/blob/main/docs/guides/authentication.md) | the token, where `diagnos login` keeps it, why classic + post-quantum |
| [Sessions](https://github.com/diagnos-tech/integration/blob/main/docs/guides/sessions.md) | how a session opens, expires and reopens; OpenBao auto-unseal |
| [Errors](https://github.com/diagnos-tech/integration/blob/main/docs/guides/errors.md#every-exception) | the exit code of every failure |
| [Configuration](https://github.com/diagnos-tech/integration/blob/main/docs/guides/configuration.md) | every environment variable |

Known limits and the questions still open on the vault side:
[Compatibility with the vault](https://github.com/diagnos-tech/integration/blob/main/docs/COMPATIBILITY.md).

## Development

```sh
make sync
uv run pytest apps/cli/tests -q
uv run ruff check src/diagnos/cli apps/cli && uv run ruff format --check src/diagnos/cli apps/cli
uv run mypy src
```

A command's examples live next to it, in its `epilog` (`diagnos.cli.examples`): they show at the bottom of `--help`
and in the generated reference, and `make docs-check` fails if the two ever disagree. See
[CONTRIBUTING.md](https://github.com/diagnos-tech/integration/blob/main/CONTRIBUTING.md) for the bilingual-docstring
rule and the "`diagnos.cli` imports only `diagnos`" boundary.
