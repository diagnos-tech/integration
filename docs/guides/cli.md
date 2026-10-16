# CLI guide

**English** · [Português (Brasil)](cli.pt-BR.md)

`diagnos` is the SDK in your terminal: the same token, the same encryption, the same errors, with human-readable
tables by default and JSON for scripts. Every command is listed with all its options in the
[CLI reference](../reference/cli.json); this guide is about using them together.

```sh
diagnos --help                  # every command
diagnos patients create --help  # one command, with examples at the bottom
```

## Global options

Global options go **anywhere** on the line — `diagnos patients list --json` is `diagnos --json patients list`. Only
what comes after `--` is left alone.

| Option | What it does |
|---|---|
| `--json` | machine-readable output: plain JSON on `stdout`, no tables, panels or spinners |
| `--quiet`, `-q` | no spinners or progress bars |
| `--token TOKEN` | the token for this one invocation (a `dgn_sk1_` token, or the deprecated `apikey-` one), overriding every other source; never echoed anywhere. Prefer `diagnos login`: a token on the command line ends up in `ps` and in shell history |
| `--vault-url URL` | overrides `DIAGNOS_VAULT_URL` for this invocation |
| `--no-color` | no ANSI escapes at all — colors, bold and dim (so does the `NO_COLOR` environment variable) |
| `--version` | prints the CLI version and exits |

Everything else — timeouts, time precision, OpenBao — comes from the environment, exactly as for the SDK
([Configuration](configuration.md)).

## Signing in

Paste the service account token once:

```sh
diagnos login
```

```text
Token (dgn_sk1_…):
Logged in · Sessão iniciada
  identity · identidade: svc_3f2a…@ws_….diagnos.health
  groups · grupos:       sg_oncology, sg_radiology
  stored in · guardado:  keyring (keyring.backends.macOS.Keyring)
```

`login` reads the token with hidden input (pasting works, and so does a pipe), checks its CRC **before any network
call** — a token cut short says "truncated or pasted wrong", not a confusing 401 — then proves it: it opens a session,
which only happens when the vault verifies both the Ed25519 and the ML-DSA-65 signature. Only then is it stored:

1. in the **system keyring** when there is one that encrypts at rest — macOS Keychain, Windows Credential Locker,
   Secret Service or KWallet on Linux. A plain-text or "null" keyring backend (such as `keyrings.alt`'s file
   backends) counts as no keyring;
2. else in **OpenBao**, at `secret/diagnos/token`, when `OPENBAO_ADDR` and an OpenBao token are set — the place for a
   server;
3. else nowhere: the command refuses and explains both options.

It never writes the token to a text file. `--store keyring` or `--store openbao` narrows the choice to one place. After
that, every command finds the token on its own:

```sh
diagnos whoami                   # which token, from where, and the groups the vault gave it
diagnos patients list            # opens its own session with one signed request
diagnos logout                   # removes the token from the keyring (and OpenBao, when configured)
```

`whoami` proves the token against the vault and prints the identity, the workspace, where the token came from and the
groups of its session. `status` reports the same identity, OpenBao, the memory enclave and the session agent without
touching the network; `status --check` also opens a session and lists the groups, and `groups` lists them one per line.

### `DIAGNOS_TOKEN` in CI and containers

In CI and short-lived containers there is no keyring and no one to type: put the token in `DIAGNOS_TOKEN`, straight
from the secret store. It wins over what `login` stored. When the token came from the environment in an interactive
terminal, the CLI says so once, and recommends `diagnos login`.

```sh
DIAGNOS_TOKEN="$(cat /run/secrets/diagnos-token)" diagnos --quiet patients list --all
```

No command asks a person for anything: every invocation opens its own session with one signed request, and opens a new
one if the vault drops it.

## The legacy token in the terminal

The deprecated `apikey-` token (`DIAGNOS_API_TOKEN`, until 2027-04-15) still needs an approved enrollment before it
can decrypt anything. The first command that needs one shows a panel on `stderr` and waits:

```text
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

An admin opens the link, checks the machine described there, types the code and picks the groups. To approve once and
keep that session for the commands that follow, run `diagnos session start`:

```sh
diagnos session start            # approve once
diagnos patients list            # reuses the session
diagnos logout                   # ends it on the vault and wipes the keys
```

**How it works.** `session start` starts a small background process for your token, the *session agent*, and the
session is unlocked inside it, in the SDK's Rust enclave: locked RAM, left out of core dumps, wiped on exit. Later
commands never receive the keys. They hand their arguments to the agent over a private Unix socket; the agent runs the
command itself and streams back its output, its prompts and its exit code. So `--json`, pipes, relative paths like
`-o out.dcm`, confirmation prompts and exit codes behave exactly as if the command ran in your shell. Nothing is
written to disk.

- **It ends** on `diagnos logout`, after `DIAGNOS_AGENT_IDLE_MINUTES` without a command (default `480`, 8 hours), or on
  `SIGTERM` (a shutdown, say). Every time, the session is revoked on the vault and its keys wiped.
  `diagnos session lock` revokes the session but keeps the agent: the next command enrolls again.
- **Only you can use it.** The socket lives in `$XDG_RUNTIME_DIR/diagnos-<uid>/` (else the temp directory), which
  must be yours with mode `0700` — anything else is refused, never repaired — and on Linux the agent also checks the
  connecting process's uid. There is one agent per token and vault URL.
- **Without `session start`**, or with `DIAGNOS_AGENT=off`, each command runs in its own process and enrolls on its
  own the first time it needs the vault. Windows has no agent yet and always works this way.

For anything that runs unattended with the legacy token, [OpenBao auto-unseal](sessions.md#auto-unseal-with-openbao)
saves the session after the first approval (`--no-auto-unseal` turns that off for one `session start`). Better:
switch to the service account token, which needs no approval at all ([MIGRATING.md](../../MIGRATING.md)).

## Patients

Lists are **anonymous by default** — ids, versions, groups and flags — so a list never prints names you did not ask
for. `--summary` decrypts each row's names and tags; `get` prints the whole record.

```sh
diagnos patients list --group sg_oncology            # one page, anonymous
diagnos patients list --group sg_oncology --summary  # names and tags too
diagnos patients list --all                          # every page
diagnos patients list --limit 20 --cursor CURSOR     # the next page; the cursor is printed under each page
diagnos patients list --include-deleted              # the trash too
diagnos patients get PATIENT_ID                      # the newest content: a newer web-editor draft wins
diagnos patients get PATIENT_ID --committed          # saved versions only
diagnos patients get PATIENT_ID --version VERSION_ID # one exact version
```

Create from inline flags, or from a JSON file with the complete record:

```sh
diagnos patients create --group sg_oncology --legal-name "Jane Doe" --display-name Jane \
  --birth-date 1990-01-31 --external-id MRN-0042 --tag diabetes --tag follow-up
diagnos patients create --group sg_oncology --file patient.json
```

```json
{
  "legal_name": "Jane Doe",
  "display_name": "Jane",
  "birth_date": "1990-01-31",
  "biological_sex": "FEMALE",
  "address": { "city": "São Paulo", "state": "SP", "country": "BR" }
}
```

A record comes from `--file` or from the inline flags, never both — mixing them is refused, naming the flags.
`--file -` reads it from stdin, as in `jq '.patient' export.json | diagnos patients create --file -`.

**Which security group a write goes to.** `patients create`, `exams create`, `files upload` and `files mkdir` seal
under `--group`, else `DIAGNOS_GROUP`, else — for an exam — its patient's group, else the only group this session
holds (the CLI prints which one it picked). With several groups and none of those, the command stops and lists them:
it never guesses, since sealing under the wrong group hands the record to the wrong team.

An update writes a complete new version from a file. `--expect-version` makes the vault refuse it if someone saved
in between (exit code `7`); `--tag` replaces the tags, and omitting it keeps them:

```sh
diagnos --json patients get PATIENT_ID | jq '.record' > patient.json   # read
$EDITOR patient.json                                                    # change
diagnos patients update PATIENT_ID --file patient.json --expect-version VERSION_ID   # write
```

Archive and delete are flags; delete asks for confirmation unless `--yes`, and is never a hard delete:

```sh
diagnos patients archive PATIENT_ID
diagnos patients unarchive PATIENT_ID
diagnos patients delete PATIENT_ID --yes
diagnos patients restore PATIENT_ID
```

The record's fields, dates and typo protection are the SDK's — see [Patients](patients.md#the-record).

## Exams

The same verbs, with two differences: `create` needs the patient, the one field that travels in clear, and `get`
prints the report as plain text (`--json` has the full record, HTML included).

```sh
diagnos exams list --group sg_radiology --summary
diagnos exams create --patient PATIENT_ID --group sg_radiology \
  --title "Chest CT" --modality CT --exam-date 2026-09-01
diagnos exams create --patient PATIENT_ID --group sg_radiology --file exam.json
diagnos exams get EXAM_ID
diagnos exams update EXAM_ID --file exam.json --expect-version VERSION_ID
diagnos exams delete EXAM_ID --yes
```

Write both `report_lexical` and `report_html` in `exam.json` when people will open the report in the web editor —
[Exams](exams.md#the-report) explains why.

## Files

```sh
diagnos files upload --group sg_oncology --exam EXAM_ID scans/*.dcm   # many at once, 100 per reservation
FOLDER=$(diagnos --json files mkdir "CT 2026-09-01" --group sg_oncology | jq -r .node_id)
diagnos files upload --group sg_oncology --folder "$FOLDER" report.pdf
diagnos files list --group sg_oncology --folder "$FOLDER"             # names decrypted
diagnos files list --exam EXAM_ID --all
diagnos files list --include-pending                                  # unfinished uploads too
diagnos files get NODE_ID                                             # metadata and name, never content
diagnos files download NODE_ID                                        # to ./<its name>
diagnos files download NODE_ID -o scan.dcm
```

`download` without `-o` writes to the file's decrypted name in the current directory — its **last path segment
only**, because the web app seals relative paths as names and a crafted `../../.bashrc` must not escape. Reading a
file needs only its node id; `--group` on `list` is a filter, not a requirement.

## Scripting

### JSON output

With `--json`, `stdout` is exactly one JSON document — never wrapped or colored by the terminal renderer, so a long
field cannot break a line. The shapes match the REST API's:

| Command | `stdout` |
|---|---|
| `patients list`, `exams list` | `{"items": [{"index": …, "summary": null or …}], "next_cursor": …}` |
| `patients get`, `exams get`, `create`, `update` | the whole `Patient` / `Exam`: `index`, `record`, `summary`, `version_id`, `draft_rev` |
| `archive`, `unarchive`, `delete`, `restore` | the updated `index` |
| `files list`, `files upload` | `{"items": [{"node": …, "name": …}], "next_cursor": …}` |
| `files get` | `{"node": …, "name": …}` |
| `files mkdir` | `{"node_id": …}` |
| `files download` | `{"node_id": …, "saved_to": …}` |
| `login` | the `whoami` fields, plus `stored_in` and `shadowed_by` (the variables that would win over the stored token) |
| `whoami` | `identity`, `key_id`, `workspace_id`, `token_kind`, `token_source`, `security_groups`, `session_expires_at` |
| `logout` | `{"removed_from": […], "agent_stopped": …, "diagnos_token_still_set": …}` |
| `groups` | `{"security_groups": […]}` |
| `status` | `workspace_id`, `key_id`, `identity`, `token_source`, `openbao_configured`, `sdk_version`, `memory`, `agent` — and `security_groups` with `--check` |

```sh
diagnos --json patients list --all | jq -r '.items[].index.document_id'
diagnos --json exams list --all | jq -r '.items[] | select(.index.meta.patient_id == "PATIENT_ID") | .index.document_id'
diagnos --json files list --exam EXAM_ID --all | jq -r '.items[] | "\(.node.node_id)\t\(.name)"'
```

Errors never go to `stdout`: they go to `stderr` as one line, and the exit code says what happened.

### Exit codes

`0` is success; `2` a configuration problem (no token found, a token pasted wrong, no safe place to store it); `3`
authentication, permission, session or enrollment; `4` not found;
`5` quota; `6` rate limited; `7` conflict; `1` anything else, a local file problem included. The full mapping from
each SDK exception is in [Errors](errors.md#every-exception).

### Unattended jobs

```sh
#!/bin/sh
# nightly-upload.sh — run from cron; the token is in OpenBao (OPENBAO_ADDR, OPENBAO_TOKEN_FILE) or in DIAGNOS_TOKEN
set -eu
diagnos --quiet --no-color files upload --group sg_radiology --exam "$EXAM_ID" /data/outbox/*.dcm
```

Use `--quiet` so no spinner writes to the log, and the exit code — not the text — to decide what happened. With the
service account token no run ever waits for a person.
