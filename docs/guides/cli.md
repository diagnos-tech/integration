# CLI guide

**English** · [Português (Brasil)](cli.pt-BR.md)

`diagnos` is the SDK in your terminal: the same enrollment, the same encryption, the same errors, with human-readable
tables by default and JSON for scripts. Every command is listed with all its options in the
[CLI reference](../reference/cli.json); this guide is about using them together.

```sh
diagnos --help                  # every command
diagnos patients create --help  # one command, with examples at the bottom
```

## Global options

Global options go **before** the subcommand — `diagnos --json patients list`, not `diagnos patients list --json`.

| Option | What it does |
|---|---|
| `--json` | machine-readable output: plain JSON on `stdout`, no tables, panels or spinners |
| `--quiet`, `-q` | no spinners or progress bars |
| `--token TOKEN` | overrides `DIAGNOS_API_TOKEN` for this invocation; never echoed anywhere |
| `--vault-url URL` | overrides `DIAGNOS_VAULT_URL` for this invocation |
| `--no-color` | no ANSI colors (so does the `NO_COLOR` environment variable) |
| `--version` | prints the CLI version and exits |

Everything else — timeouts, time precision, OpenBao — comes from the environment, exactly as for the SDK
([Configuration](configuration.md)).

## Enrollment in the terminal

Each `diagnos` invocation is its own process, and a process needs an approved session before it can decrypt
anything. The first command that needs one shows a panel on `stderr` and waits:

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

An admin opens the link, checks the machine described there, types the code and picks the groups. `login` does only
this, and then shows what was granted:

```sh
diagnos login
diagnos --json login | jq -r '.security_groups[]'
```

```text
Enrolled · Sessão estabelecida
  workspace_id: ws_...
  account_id:   acct_...
  groups · grupos: sg_oncology, sg_radiology
```

`status` parses the token locally and reports OpenBao and the memory enclave without touching the network;
`status --check` also unlocks and lists the granted groups, and `groups` lists them one per line.

```sh
diagnos status
diagnos status --check
diagnos groups
```

### Not approving every command

Without OpenBao, **the session dies with the process**: the next invocation enrolls again, with a new link and code.
That is the right default on a laptop — `login` is for checking a token and seeing what it grants. For anything that
runs unattended, configure [OpenBao auto-unseal](sessions.md#auto-unseal-with-openbao): the first invocation enrolls
once and saves the session, and every later one restores it silently until it expires.

```sh
export OPENBAO_ADDR="https://openbao.internal:8200"
export OPENBAO_TOKEN_FILE=/run/secrets/openbao-token
diagnos login                    # a person approves once; the session is saved to OpenBao
diagnos --quiet patients list    # restored — no prompt
diagnos login --no-auto-unseal   # enroll without saving, even with OPENBAO_ADDR set
```

`diagnos session lock` ends the session: it wipes the saved copy in OpenBao, so the next invocation enrolls again.

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
| `login` | `{"workspace_id": …, "account_id": …, "security_groups": […]}` |
| `groups` | `{"security_groups": […]}` |
| `status` | `workspace_id`, `account_id`, `openbao_configured`, `sdk_version`, `memory` — and `security_groups` with `--check` |

```sh
diagnos --json patients list --all | jq -r '.items[].index.document_id'
diagnos --json exams list --all | jq -r '.items[] | select(.index.meta.patient_id == "PATIENT_ID") | .index.document_id'
diagnos --json files list --exam EXAM_ID --all | jq -r '.items[] | "\(.node.node_id)\t\(.name)"'
```

Errors never go to `stdout`: they go to `stderr` as one line, and the exit code says what happened.

### Exit codes

`0` is success; `2` a configuration problem; `3` authentication, permission, session or enrollment; `4` not found;
`5` quota; `6` rate limited; `7` conflict; `1` anything else. The full mapping from each SDK exception is in
[Errors](errors.md#every-exception).

### Unattended jobs

```sh
#!/bin/sh
# nightly-upload.sh — run from cron, with OPENBAO_ADDR and OPENBAO_TOKEN_FILE in the environment
set -eu
diagnos --quiet --no-color files upload --group sg_radiology --exam "$EXAM_ID" /data/outbox/*.dcm
```

Use `--quiet` so no spinner writes to the log, OpenBao so no run waits for a person, and the exit code — not the
text — to decide what happened.
