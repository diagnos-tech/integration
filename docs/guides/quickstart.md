# Quickstart

**English** · [Português (Brasil)](quickstart.pt-BR.md)

From a service-account token to your first encrypted patient and file, in about five minutes. Every byte of clinical
data below is encrypted inside your own process before it touches the network; the vault only ever stores
ciphertext.

## Before you start

| You need | Where it comes from |
|---|---|
| Python 3.11, 3.12 or 3.13 | [python.org](https://www.python.org/downloads/) or your package manager |
| A service-account token (`apikey-…`) | A workspace admin creates it in the diagnos web app |
| Someone who can approve an enrollment | A workspace admin, with the web app open |

> [!NOTE]
> The token identifies *which* service account is asking. It does not unlock anything by itself: the first run
> prints a link and a 6-digit code that an admin approves — see [Authentication](authentication.md) for why.

## 1. Install

```sh
pip install diagnos          # the SDK
pipx install diagnos-cli     # optional: the `diagnos` command
```

Until the first PyPI release, install from source — [Install](install.md) has the exact commands, including the
Rust toolchain the source build needs.

## 2. Hand the token to the process

```sh
export DIAGNOS_API_TOKEN="apikey-…"
```

The SDK reads it from the environment; the CLI also accepts `--token` for a single invocation. Nothing ever prints
it back: every `repr` in the SDK is redacted.

## 3. Enroll and write your first patient

```python
from diagnos import Diagnos

with Diagnos() as vault:  # prints an approval link and a 6-digit code, then waits
    print("workspace:", vault.workspace_id)
    print("groups:", vault.security_groups)

    group = vault.security_groups[0]  # the security groups the admin granted
    patient = vault.patients.create(
        {"legal_name": "Jane Doe", "display_name": "Jane", "birth_date": "1990-01-31"},
        security_group=group,
        tags=["follow-up"],
    )
    print("created", patient.id, "version", patient.version_id)
```

While `Diagnos()` waits, open the printed link in the web app, check that the machine described there is yours,
type the code and pick the security groups this process may read. The block continues the moment you approve.

`security_groups` is the list the admin granted; a document belongs to exactly one of them. Everything in the
record — names, birth date — is sealed under a fresh key before it leaves; the vault learns only that a patient
exists in that group.

## 4. Read it back

```python
with Diagnos() as vault:
    for row in vault.patients.list():  # names come from a sealed summary: no version is downloaded
        print(row.id, row.summary.display_name if row.summary else "—")

    same = vault.patients.get(patient.id)  # downloads and decrypts the newest version
    print(same.record.legal_name, same.tags)
```

> [!TIP]
> Each `Diagnos()` above enrolls again, because a session lives only in the memory of the process that earned it.
> In real code, keep one `vault` for the life of the process — and read [Sessions](sessions.md) before running on a
> server that restarts without a human.

## 5. Upload and download a file

```python
with Diagnos() as vault:
    drive = vault.drives.drive(vault.security_groups[0])
    node = drive.upload("scans/IM-0001.dcm")  # its own key; name and content sealed
    print(node.node_id, drive.name_of(node), node.mime_type, node.size)

    data = vault.drives.download(node.node_id)  # bytes in RAM, decrypted
    vault.drives.download(node.node_id, "copy-of-IM-0001.dcm")  # or straight to a file
```

## 6. The same from the terminal

```sh
diagnos login                                   # enroll; prints what was granted
diagnos patients create --group sg_oncology --legal-name "Jane Doe" --display-name Jane
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology scans/IM-0001.dcm
```

Each `diagnos` invocation is its own process, so each one enrolls unless OpenBao is configured — the
[CLI guide](cli.md) explains how to run it in scripts and cron jobs.

## Where to go next

| To… | Read |
|---|---|
| understand workspaces, groups, versions and nodes | [Concepts](concepts.md) |
| read, update, archive and delete safely | [Patients](patients.md) · [Exams](exams.md) · [Files](files.md) |
| run on a server without a human | [Sessions and OpenBao auto-unseal](sessions.md) |
| handle every failure | [Errors](errors.md) |
| call it over HTTP instead | [REST API guide](api.md) |
| know exactly what the vault can see | [Security model](security.md) |
