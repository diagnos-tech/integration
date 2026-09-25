# diagnos-cli

**English** · [Português (Brasil)](README.pt-BR.md)

The `diagnos` command line — the zero-knowledge diagnos vault, from your terminal, built on top of the
[`diagnos`](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.md) SDK. Every byte of cryptography,
signing and retry logic lives in the SDK; this package only parses arguments and renders what the SDK returns.

> [!WARNING]
> `patients`, `exams` and `files` in this CLI wrap SDK layers that still speak an **earlier revision** of the vault
> protocol and are not compatible with today's vault (`https://vault.diagnos.health`) yet — those commands fail
> before anything is written. `login`, `status`, `groups` and `session lock` work today. See
> [Compatibility with the vault](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.md)
> for the full picture and the plan to close the gap.

> [!NOTE]
> **Not on PyPI yet.** `pipx install diagnos-cli` below is the intended, permanent install command — but until the
> first release, install from source instead (building the SDK needs a [Rust toolchain](https://rustup.rs/); `cli`
> depends on the not-yet-published `diagnos` SDK, so both come from git in one command):
> ```sh
> pipx install "diagnos-cli @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=cli" \
>   --preinstall "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=sdk"
> ```
> Coming from `imgexam-cli`? Versions restart at `0.1.0` under the new name — read
> [MIGRATING.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.md) before upgrading.

## Install

```sh
pipx install diagnos-cli
export DIAGNOS_API_TOKEN="apikey-…"   # issued by a workspace admin
```

Auto-unseal via OpenBao needs the `openbao` extra: `pipx install "diagnos-cli[openbao]"` — see
[OpenBao, for servers](#openbao-for-servers) below.

`DIAGNOS_API_TOKEN` identifies *this* service account and its workspace; it does not, by itself, unlock anything —
that is what `diagnos login` is for. `--token` on any command overrides it for that one invocation, and is never
echoed anywhere (not in `--help`, not in output, not in `--json`).

## Your first `diagnos login`

```sh
$ diagnos login
```

The first time a `diagnos` process runs (and every time after, unless OpenBao is configured — see below), it has to
*enroll*. `login` runs that dance explicitly, so you can watch it happen: a panel with a link and a 6-digit code
appears, then a spinner while it waits.

```
╭────────────────────── diagnos · enrollment ───────────────────────╮
│ Open this link and type the code below to approve this session.   │
│ Abra este link e digite o código abaixo para aprovar esta sessão. │
│                                                                   │
│ https://…                                                         │
│                                                                   │
│   4  8  2  9  1  5                                                │
╰───────────────────────────────────────────────────────────────────╯
⠋ waiting for approval… · aguardando aprovação…
```

That panel — and the status line under it — really do print in both languages, on every install: this is a transcript
of the actual `rich` output, not a translation choice this document is making.

Open that link, type the code, and pick which security groups this CLI process may read. Once a workspace admin
approves, `login` prints what was granted:

```
Enrolled · Sessão estabelecida
  workspace_id: ws_...
  account_id:   acct_...
  groups · grupos: sg_oncology, sg_radiology
```

**The CLI never persists the session to disk.** Without OpenBao configured (next section), that session lives only
in this process's memory — the moment it exits, it is gone, and the *next* `diagnos` invocation enrolls again, from
scratch, with a brand new link and code. This is not a bug to route around: `login` on its own is for *validating a
token and seeing what it was granted*, one process at a time. Every other command (`patients`, `exams`, `files`,
`groups`) also enrolls lazily on its own if no session is available — you do not have to run `login` first.

## OpenBao, for servers

A human approval on every restart is fine for a one-off script; it is not fine for a cron job or a Kubernetes pod.
Set `OPENBAO_ADDR`/`OPENBAO_TOKEN` (see the SDK's
[Auto-unseal with OpenBao](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.md#auto-unseal-with-openbao)
section for the full tradeoff) and every command's `unlock()` saves the session to OpenBao's encrypted KV store after
a successful enrollment, and restores from there on the next invocation — no human, no new link, until the saved
session itself expires. `login --auto-unseal`/`--no-auto-unseal` overrides the automatic default (on iff
`OPENBAO_ADDR` is set) for one invocation.

## Commands

| Command | Status | What it does |
|---|---|---|
| `diagnos login [--auto-unseal/--no-auto-unseal]` | ✅ works today | Enrolls, shows what was granted. |
| `diagnos status [--check]` | ✅ works today | Parsed token, OpenBao, SDK version; `--check` also unlocks. |
| `diagnos groups` | ✅ works today | Lists granted security groups. |
| `diagnos session lock` | ✅ works today | Ends the session, best-effort. |
| `diagnos patients list [--group G] [--include-deleted] [--limit N] [--cursor C] [--all]` | ⚠️ see warning | Pages patient indexes. |
| `diagnos patients get PATIENT_ID [--version V]` | ⚠️ see warning | Decrypts and shows one patient. |
| `diagnos patients create --group G (--file record.json \| --legal-name ... --display-name ... [--birth-date D])` | ⚠️ see warning | Creates a patient. |
| `diagnos patients update PATIENT_ID --file record.json` | ⚠️ see warning | New version of the record. |
| `diagnos patients archive\|unarchive PATIENT_ID` | ⚠️ see warning | Flips the archived flag, in a new version. |
| `diagnos patients delete PATIENT_ID [--yes]` | ⚠️ see warning | Marks the index deleted, in a new version (`--yes` skips the confirmation prompt). |
| `diagnos exams list [--group G] [--include-deleted] [--limit N] [--cursor C] [--all]` | ⚠️ see warning | Pages exam indexes. |
| `diagnos exams get EXAM_ID [--version V]` | ⚠️ see warning | Decrypts and shows one exam. |
| `diagnos exams create --patient P --group G [--modality M] (--file record.json \| --title T)` | ⚠️ see warning | Creates an exam, linked to a patient. |
| `diagnos exams update EXAM_ID --file record.json [--modality M]` | ⚠️ see warning | New version of the record. |
| `diagnos exams archive\|unarchive EXAM_ID` | ⚠️ see warning | Flips the archived flag, in a new version. |
| `diagnos exams delete EXAM_ID [--yes]` | ⚠️ see warning | Marks the index deleted, in a new version (`--yes` skips the confirmation prompt). |
| `diagnos files list --group G [--exam E] [--include-pending] [--limit N] [--cursor C] [--all]` | ⚠️ see warning | Lists drive nodes, name decrypted. |
| `diagnos files upload --group G PATH... [--exam E]` | ⚠️ see warning | Uploads one batch. |
| `diagnos files download --group G NODE_ID [-o DEST]` | ⚠️ see warning | Downloads and decrypts. |
| `diagnos files get --group G NODE_ID` | ⚠️ see warning | One node's metadata. |

Rows marked ⚠️ fail against today's production vault — see the warning at the top of this document.

Global options, on the root command, before the subcommand:

| Option | What it does |
|---|---|
| `--json` | Machine-readable output, no tables/panels/spinners. |
| `--quiet` / `-q` | Suppresses spinners and progress bars. |
| `--vault-url URL` | Overrides `DIAGNOS_VAULT_URL`. |
| `--token TOKEN` | Overrides `DIAGNOS_API_TOKEN`; never echoed. |
| `--no-color` | Disables ANSI colors. |
| `--version` | Prints the CLI version and exits. |

## `--json`, for scripts

Every command accepts `--json` before the subcommand name — the output is plain `json.dumps`, never wrapped by
`rich`, so a long field can never break a line mid-document the way a terminal-width-aware renderer could:

```sh
diagnos --json patients list --group sg_oncology | jq '.items[].document_id'
```

## Exit codes

Stable and documented, for `if`/`case` in a script — never grep the error text:

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Other error (includes invalid input, e.g. `ValidationError`). |
| `2` | Configuration error (missing/malformed token, env var). |
| `3` | Authentication/permission/session (`AuthenticationError`, `DiagnosPermissionError`, `SessionExpiredError`, enrollment denied/expired). |
| `4` | Not found. |
| `5` | Quota exceeded. |
| `6` | Rate limited. |
| `7` | Conflict (pending version, replay). |

## Development

```sh
uv sync --all-packages
uv run --package diagnos-cli pytest apps/cli/tests -q
uv run ruff check cli && uv run ruff format --check cli
uv run mypy apps/cli/src
```

See [CONTRIBUTING.md](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.md) for the
bilingual-docstring rule and the "`cli` imports only `diagnos`" boundary, and the
[workspace README](https://github.com/diagnos-tech/integration/blob/develop/README.md) for the overall layout and
the `make` targets (`sync`, `test`, `check`, `help`) contributors use.
