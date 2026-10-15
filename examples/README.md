# Examples

**English** · [Português (Brasil)](README.pt-BR.md)

Small, complete programs for the Python SDK, one folder each: a `main.py` you can read in a minute and run as it
is. They use the same credential flow as production code — nothing is faked, nothing is skipped.

| Folder | Shows |
|---|---|
| [`01-quickstart`](01-quickstart/README.md) | credential → enrollment → first call |
| [`02-upload-file`](02-upload-file/README.md) | a file into the drive, listed and downloaded back |
| [`03-patients`](03-patients/README.md) | create, list and read patients |
| [`04-exams`](04-exams/README.md) | an exam with a report and a file attached to it |
| [`05-error-handling`](05-error-handling/README.md) | every failure the SDK raises, and what to do about it |
| [`06-lock-session`](06-lock-session/README.md) | ending the session on purpose with `lock()` |

There is no example for async (the SDK is synchronous), for creating a share link (the SDK has no call for it; links
are made in the web app) or for the public viewer (a route for the person who receives a link, not for the SDK).

## Before you run any of them

```sh
pip install "diagnos[sdk]"
export DIAGNOS_CREDENTIAL='svc_<32 hex>@<workspace_id>.diagnos.health:<43-character key>'
```

- **The credential** is the line a workspace admin copies when creating a service account (Settings → Service
  accounts). `DIAGNOS_CREDENTIALS_FILE` (the downloaded JSON) and `~/.config/diagnos/credentials.json` work too. The
  old `DIAGNOS_API_TOKEN` (`apikey-…`) still works until **2027-04-15**, with a deprecation warning — see
  [Authentication](../docs/guides/authentication.md).
- **An approver.** The first call prints a link and a 6-digit code on `stderr`; an admin opens the link in the web
  app, types the code and picks the security groups the process may read. The program continues on its own.
- **A group.** The examples use the first group granted; set `DIAGNOS_GROUP` to choose another.

Then, from an example's folder:

```sh
python main.py
```

## Against a local stack

`DIAGNOS_VAULT_URL` points the SDK at another vault; it defaults to `https://vault.diagnos.health`. Point it at a
local or staging stack to try the examples that write data:

```sh
export DIAGNOS_VAULT_URL=http://127.0.0.1:8787
```

> [!WARNING]
> Examples 02, 03 and 04 **create** patients, exams and files. Run them against a workspace you can throw away, not
> against real clinical data.

## Checks

`make lint` and `make types` cover this folder: ruff, the bilingual docstring rule and `mypy --strict`, one example
at a time (each is a `main.py`). `make test` runs every example end to end against the SDK's in-memory
vault double. An `example.json` beside a `main.py` is read by the end-to-end harness (the command, a timeout, the
documents it must find created, the lines it must print).
