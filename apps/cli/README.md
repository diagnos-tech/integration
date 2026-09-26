# diagnos-cli

**English** · [Português (Brasil)](README.pt-BR.md)

The `diagnos` command line — the zero-knowledge diagnos vault, from your terminal, built on top of the
[`diagnos`](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.md) SDK. Every byte of cryptography,
signing and retry logic lives in the SDK; this package only parses arguments and renders what the SDK returns.

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

Before it can decrypt anything, the CLI has to *enroll*: a human approves this session in the browser. `login` runs
that dance explicitly, so you can watch it happen: a panel with a link and a 6-digit code appears, then a spinner
while it waits.

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

## One session for every command that follows

After `login`, the next commands reuse that session — no new link, no new code — until you log out:

```sh
diagnos login                    # approve once
diagnos patients list            # reuses the session
diagnos files upload scan.dcm    # …and so on
diagnos logout                   # revokes it on the vault and wipes the keys
```

**How it works.** `login` starts a small background process for your token, the *session agent*, and the session is
unlocked inside it, in the SDK's Rust enclave: locked RAM, left out of core dumps, wiped on exit. Later commands never
receive the keys. They hand their arguments to the agent over a private Unix socket; the agent runs the command
itself and streams back its output, its prompts and its exit code. So `--json`, pipes, relative paths like
`-o out.dcm`, confirmation prompts and exit codes behave exactly as if the command ran in your shell. **Nothing is
written to disk, and no OS keychain is involved.**

- **It ends** on `diagnos logout`, after `DIAGNOS_AGENT_IDLE_MINUTES` without a command (default `480`, 8 hours), or on
  `SIGTERM` (a shutdown, say). Every time, the session is revoked on the vault and its keys wiped.
  `diagnos session lock` revokes the session but keeps the agent: the next command enrolls again.
- **Only you can use it.** The socket lives in `$XDG_RUNTIME_DIR/diagnos-<uid>/` (else the temp directory), which
  must be yours with mode `0700` — anything else is refused, never repaired — and on Linux the agent also checks the
  connecting process's uid. There is one agent per token and vault URL: `--token` with another token never reaches
  this session.
- **`diagnos status`** says whether an agent is running and holds a session.
- **Without `login`** (a script, a CI job), or with `DIAGNOS_AGENT=off`, each command runs in its own process and
  enrolls on its own the first time it needs the vault; the session dies with that process. For unattended jobs, see
  OpenBao below. Windows has no agent yet and always works this way.

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
| `diagnos logout` | ✅ works today | Revokes the kept session, wipes its keys and stops the agent. |
| `diagnos groups` | ✅ works today | Lists granted security groups. |
| `diagnos session lock` | ✅ works today | Ends the session, best-effort (the agent keeps running). |
| `diagnos patients list [--group G] [--include-deleted] [--limit N] [--cursor C] [--all] [--summary]` | ✅ works today | Pages patients; anonymous unless `--summary` decrypts names and tags. |
| `diagnos patients get PATIENT_ID [--version V] [--committed]` | ✅ works today | Decrypts and shows one patient (a newer draft wins unless `--committed`). |
| `diagnos patients create [--group G] (--file record.json \| --legal-name ... --display-name ... [--birth-date D] [--external-id X]) [--tag T]...` | ✅ works today | Creates a patient. |
| `diagnos patients update PATIENT_ID --file record.json [--tag T]... [--expect-version V]` | ✅ works today | New complete version; `--tag` replaces the tags, `--expect-version` refuses a stale write. |
| `diagnos patients archive\|unarchive PATIENT_ID` | ✅ works today | Flips the archived flag (no new version). |
| `diagnos patients delete PATIENT_ID [--yes]` | ✅ works today | Moves the patient to the trash (`--yes` skips the confirmation prompt). |
| `diagnos patients restore PATIENT_ID` | ✅ works today | Takes the patient out of the trash. |
| `diagnos exams list [--group G] [--include-deleted] [--limit N] [--cursor C] [--all] [--summary]` | ✅ works today | Pages exams; anonymous unless `--summary` decrypts title, modality and date. |
| `diagnos exams get EXAM_ID [--version V] [--committed]` | ✅ works today | Decrypts and shows one exam, the report as plain text. |
| `diagnos exams create --patient P [--group G] (--file record.json \| --title T [--modality M] [--exam-date D])` | ✅ works today | Creates an exam; only `--patient` is sent in clear. |
| `diagnos exams update EXAM_ID --file record.json [--expect-version V]` | ✅ works today | New complete version of the record. |
| `diagnos exams archive\|unarchive EXAM_ID` | ✅ works today | Flips the archived flag (no new version). |
| `diagnos exams delete EXAM_ID [--yes]` | ✅ works today | Moves the exam to the trash (`--yes` skips the confirmation prompt). |
| `diagnos exams restore EXAM_ID` | ✅ works today | Takes the exam out of the trash. |
| `diagnos files list [--group G] [--folder F] [--exam E] [--include-pending] [--limit N] [--cursor C] [--all]` | ✅ works today | Lists files and folders, names decrypted — the whole workspace unless filtered. |
| `diagnos files upload [--group G] PATH... [--exam E] [--folder F]` | ✅ works today | Encrypts and uploads, 100 files per reservation; large files go up in parts. |
| `diagnos files mkdir NAME [--group G] [--parent F]` | ✅ works today | Creates a folder and prints its node id (pass it to `--folder`). |
| `diagnos files download NODE_ID [-o DEST]` | ✅ works today | Downloads and decrypts, by default to the file's own name (its last path segment only). |
| `diagnos files get NODE_ID` | ✅ works today | One file's metadata and decrypted name. |

Reading a file needs only its node id; the vault knows which group it belongs to.

**Which security group a write goes to.** `patients create`, `exams create`, `files upload` and `files mkdir` seal
under `--group`, else `DIAGNOS_GROUP`, else — for an exam — its patient's group, else the only group this session
holds (the CLI prints which one it picked). With several groups and none of those, the command stops and lists them:
it never guesses, since sealing under the wrong group hands the record to the wrong team.
Known limits and the questions still open on the vault side:
[Compatibility with the vault](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.md).

Global options go anywhere on the line — `diagnos patients list --json` is `diagnos --json patients list` (only
what comes after `--` is left alone):

| Option | What it does |
|---|---|
| `--json` | Machine-readable output, no tables/panels/spinners. |
| `--quiet` / `-q` | Suppresses spinners and progress bars. |
| `--vault-url URL` | Overrides `DIAGNOS_VAULT_URL`. |
| `--token TOKEN` | Overrides `DIAGNOS_API_TOKEN`; never echoed. |
| `--no-color` | Disables ANSI colors. |
| `--version` | Prints the CLI version and exits. |

## `--json`, for scripts

Every command accepts `--json`, anywhere on the line — the output is plain `json.dumps`, never wrapped by
`rich`, so a long field can never break a line mid-document the way a terminal-width-aware renderer could:

```sh
diagnos --json patients list --group sg_oncology | jq '.items[].index.document_id'
```

## Exit codes

Stable and documented, for `if`/`case` in a script — never grep the error text:

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Other error (includes invalid input, e.g. `ValidationError`). |
| `2` | Configuration error (missing/malformed token, env var). |
| `3` | Authentication/permission/session (`AuthenticationError`, `DiagnosPermissionError`, `GroupKeyUnavailable`, `SessionExpiredError`, enrollment denied/expired). |
| `4` | Not found. |
| `5` | Quota exceeded. |
| `6` | Rate limited. |
| `7` | Conflict (pending or newer version, replay, an upload that never reached storage). |

## Development

```sh
uv sync --all-packages
uv run --package diagnos-cli pytest apps/cli/tests -q
uv run ruff check apps/cli && uv run ruff format --check apps/cli
uv run mypy apps/cli/src
```

See [CONTRIBUTING.md](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.md) for the
bilingual-docstring rule and the "`cli` imports only `diagnos`" boundary, and the
[workspace README](https://github.com/diagnos-tech/integration/blob/develop/README.md) for the overall layout and
the `make` targets (`sync`, `test`, `check`, `help`) contributors use.
