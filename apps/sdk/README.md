# diagnos

**English** · [Português (Brasil)](README.pt-BR.md)

The official zero-knowledge Python SDK for the diagnos vault
(`vault.diagnos.health`). Patients, exams and files are encrypted in
this process, in RAM, before a single byte reaches the network — the vault
only ever sees ciphertext, signed requests and presigned URLs. This package
is the one place that complexity lives.

> [!NOTE]
> **Status: 0.1.0 preview.** Enrollment, session keys, request signing, the
> clock, the lock, `vault.patients`, `vault.exams` and `vault.drives` speak
> the vault's current protocol and are verified against it by the Pact
> contract tests (`contracts/`). Known limits:
> [COMPATIBILITY.md](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.md).

The goal is for your code to read like this:

```python
from diagnos import Diagnos

with Diagnos() as vault:
    for row in vault.patients.list():
        patient = vault.patients.get(row.id)
        print(patient.record.legal_name)
```

## Install

```sh
pip install diagnos
export DIAGNOS_API_TOKEN="apikey-…"   # issued by a workspace admin
```

> [!NOTE]
> Not on PyPI yet. Until the first release, install from source (building
> the enclave needs a [Rust toolchain](https://rustup.rs/)):
> `pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"`

`DIAGNOS_API_TOKEN` identifies *this* service account and its workspace; it
does not, by itself, unlock anything — see [Enrollment](#enrollment-the-link-and-the-code) below.

## 30 seconds to your first `list()`

```python
from diagnos import Diagnos

vault = Diagnos()  # reads DIAGNOS_API_TOKEN
vault.unlock()  # prints a link + a 6-digit code, waits for approval

for row in vault.patients.list():
    print(row.id, row.summary.display_name if row.summary else "—")
```

You do not even have to call `unlock()` yourself: the first time you touch
`vault.patients`, `vault.exams` or `vault.drives`, the SDK unlocks lazily.
`unlock()` (and the lazy path) are idempotent — call them as many times as
you like, from as many call sites as you like.

## Enrollment: the link and the code

The first time an SDK process runs (and every time after, unless
auto-unseal is configured — see below), it has to *enroll*:

1. It generates a hybrid key pair (X25519 + ML-KEM-768) in RAM and registers
   it with the vault, together with a description of where it is running
   (OS, container, hostname, user) — so the person approving can recognize
   the machine asking.
2. It prints a link and a 6-digit code to `stderr`. A workspace admin opens
   the link in the diagnos web app, reads the runtime description, types the
   code, and picks which security groups this SDK process may read.
3. The web app seals the DEKs of those groups **to the SDK's public keys**;
   the vault seals the session keys the same way. The SDK polls, opens both
   with the private keys that never left the process, and is unlocked.

Until a human approves, `unlock()` blocks. There is no way around that step —
it is the whole security model, not friction to route around.

```python
from diagnos import Diagnos, EnrollmentPrompt


def show_prompt(prompt: EnrollmentPrompt) -> None:
    print(f"Open {prompt.approval_url} and type {prompt.code}")


vault = Diagnos(on_prompt=show_prompt)  # default prompt already prints to stderr
vault.unlock()
```

## Auto-unseal with OpenBao

A human approval on every restart is fine for a laptop script; it is not
fine for a Kubernetes pod or a cron job. Set `OPENBAO_ADDR`/`OPENBAO_TOKEN`
and the SDK saves its unlocked state (session keys, group DEKs, the SDK's own
key pair) to OpenBao's encrypted KV store right after a successful
enrollment, and restores from there on the next start — no human needed,
until the saved session itself expires.

**The tradeoff, stated plainly**: this moves your group DEKs from "only ever
in this process's RAM" to "also in OpenBao's storage, at
`<OPENBAO_PATH_PREFIX>/<workspace_id>/<account_id>`". Whoever can read that
one path can decrypt exactly what this SDK process can. Scope the OpenBao
token to that path and nothing wider — that is what keeps this an
intentional trade, not a silent leak.

```sh
pip install "diagnos[openbao]"
export OPENBAO_ADDR="https://openbao.internal:8200"
export OPENBAO_TOKEN="…"           # scoped to this one path
```

```python
vault = Diagnos()  # auto_unseal defaults to True once OPENBAO_ADDR is set
vault.unlock()  # restores silently if a valid session was saved; else enrolls
```

## Where secrets live

Every key this SDK holds — session keys, the DEK of each security
group, the DEK of each document, the SDK's own X25519 + ML-KEM-768 identity —
lives in a small Rust extension shipped inside the wheel, `diagnos._secure`
(`native/`). A key there is a `SecretBox`: bytes in memory that is locked
in RAM (`mlock`, never swapped), excluded from core dumps, fenced by guard
pages, zeroed in a `fork()` child and zeroed the instant the box is dropped.
It never comes back to Python as `bytes` — signing a request, opening a
seed, unwrapping a document key, encrypting a file all happen inside the
extension. Unlocking a session also hardens the process: core dumps off,
`ptrace` attach denied. None of this changes how you use the SDK; it changes
what an attacker with a swap file, a core dump or a debugger can find.

Locking memory counts against `ulimit -l` (often 64 KiB in containers).
When the kernel refuses, the SDK keeps every other protection, logs it and
emits one `MemoryLockWarning`; set `DIAGNOS_MEMORY_LOCK=require` to refuse to
run that way instead. To let a non-root container lock memory, grant
`CAP_IPC_LOCK` (see
[`apps/api/deploy/README.md`](https://github.com/diagnos-tech/integration/blob/develop/apps/api/deploy/README.md)).
[`native/README.md`](native/README.md) states exactly what is and is not
guaranteed.

## Patients

```python
from datetime import date

from diagnos import PatientRecord

patient = vault.patients.create(
    {"legal_name": "Jane Doe", "display_name": "Jane", "birth_date": date(1990, 1, 31)},  # a dict is validated
    security_group="sg_oncology",  # exactly one group per document
    tags=["diabetes"],  # sealed list/search labels, never sent in clear
    specialist_ids=["specialist_123"],  # clear metadata the vault itself filters by
)

patient = vault.patients.get(patient.id)  # the newest content: a newer web-editor draft wins
renamed = patient.record.model_copy(update={"display_name": "Jane R."})
patient = vault.patients.update(
    patient.id,
    renamed,  # always the complete record: every version is a full snapshot
    expected_latest_version_id=patient.index.latest_version_id,  # refused if someone saved meanwhile
)

vault.patients.archive(patient.id)  # a flag, no new version
vault.patients.unarchive(patient.id)
vault.patients.delete(patient.id)  # to the trash; the encrypted history stays
vault.patients.restore(patient.id)

for row in vault.patients.iter_all(security_group="sg_oncology"):
    print(row.id, row.summary.display_name if row.summary else "—")  # decrypted locally, no download
```

- **What you write is what the web app reads.** `PatientRecord` mirrors the web app's record field for field. A
  misspelled field (`birthdate`) is refused with the field it resembles; any other unknown field is kept, so a
  read-modify-write with `model_copy` never drops a field the web app added after this SDK was released.
- **Dates** (`birth_date`, `exam_date`) accept a `date`, an aware `datetime` or an ISO string, and are stored as the
  web app stores them: a UTC instant. Set `DIAGNOS_TIME_PRECISION` to the workspace's anonymization precision and
  they are truncated before sealing, as the web app does.
- **Identity documents** (`identifiers`, e.g. CPF) are sealed by the vault, not by the SDK: existing values survive a
  round trip; a plain-text value is refused. Use `external_id` for an id from another system.
- **Drafts**: `get()` returns the web editor's draft when it is newer than the latest version (`patient.from_draft`);
  `include_draft=False` reads committed versions only. The SDK never writes drafts.

## Exams

```python
from diagnos import ExamRecord

exam = vault.exams.create(
    ExamRecord(title="Chest CT", modality="CT", exam_date="2026-09-01", report_html="<p>Unremarkable.</p>"),
    patient_id=patient.id,  # required, clear in the index — the vault routes by it; the rest is sealed
    security_group="sg_oncology",
)

exam = vault.exams.get(exam.id)
print(exam.patient_id, exam.report_status, exam.record.report_html)
```

`report_lexical` is the web editor's state and the source of truth for the report; `report_html` is derived from it
for readers that never open the editor. Write both when you produce a report the web editor should open.

## Files and folders

Every file (DICOM, image, video, PDF) and every folder of the workspace is a
*node*. A node belongs to one security group — `vault.drives.drive(group)`
writes into one — and reading needs only its id. Each file gets its own key;
its name, its content and R2's SSE-C layer are all sealed the way the web
app seals them. Small files go up in one `PUT`, large ones in encrypted
parts, 100 files per reservation — you never choose.

```python
from diagnos import UploadSource

drive = vault.drives.drive("sg_oncology")

folder_id = drive.create_folder("CT 2026-09-01")
node = drive.upload("scans/IM-0001.dcm", exam_id=exam.id, parent_id=folder_id)  # name and MIME from the path
node = drive.upload(b"raw bytes work too", name="note.txt")

nodes = drive.upload_many(
    [UploadSource("slide_1.jpg"), UploadSource(jpeg_bytes, name="slide_2.jpg")],
    exam_id=exam.id,
)  # one reservation for up to 100 files; returned in input order, ready

for child in drive.iter_all(parent_id=folder_id):  # or drive.list(...) for one page
    print(drive.name_of(child), child.size, child.mime_type)

data = vault.drives.download(node.node_id)  # bytes in RAM
vault.drives.download(node.node_id, "IM-0001.dcm")  # straight to a file, one chunk in RAM
for chunk in vault.drives.iter_download(node.node_id):  # or stream it yourself
    ...
```

`vault.drives.list()` / `iter_all()` walk the whole workspace (every group
this session may list) and filter by `security_group`, `exam_id`,
`parent_id` and `include_pending`. A `.dcm` file is typed
`application/dicom`, so the vault classifies it; pass `mime_type=` to
override. `name_of()` returns what the uploader sealed — the web app stores
a relative path there, so never write to it as a local path without taking
its last segment. Wire details:
[`docs/PROTOCOL.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.md) §9–§10.

## Errors

Every exception is reachable from `diagnos` — catch by class, never by
message
([`docs/PROTOCOL.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.md)
§12):

| Class | When |
|---|---|
| `ValidationError` | the request itself is wrong |
| `AuthenticationError` | token/session/signature rejected — usually re-enroll |
| `QuotaError` | the workspace has no credit for this |
| `DiagnosPermissionError` | this service account may not do this here |
| `NotFoundError` | 404 |
| `ConflictError` | a pending or newer version, a replay, or an upload that never reached storage (`UploadIncomplete`) — the SDK already retried what is safe to retry |
| `RateLimitError` | raised only after the SDK's own backoff gave up |
| `GroupKeyUnavailable` | this enrollment was never handed the DEK of a group the document needs |
| `EnrollmentDeniedError` / `EnrollmentExpiredError` | nobody approved, or approved too late |
| `SessionExpiredError` | no live local session — call `unlock()` (again) before a signed call |
| `ProtocolError` | the vault answered something the protocol does not allow — not retryable; report it with the SDK version |
| `VaultError` | base class; carries `code`, `status`, `trace_id` for a support ticket |

## Configuration

| Env var | Default | |
|---|---|---|
| `DIAGNOS_API_TOKEN` | — (required) | The `apikey-<jwt>` a workspace admin issued. |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | Where the vault lives. |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | Per-request HTTP timeout. |
| `DIAGNOS_TIME_PRECISION` | unset | The workspace's anonymization precision (`month`, `day`, `hour`, `minute`, `second`); dates are truncated to it before sealing. |
| `DIAGNOS_STORAGE_HOSTS` | `diagnosusercontent.com, r2.cloudflarestorage.com` | Hosts (and their subdomains) a presigned storage URL may point at, HTTPS only; anything else is refused before a byte leaves. |
| `OPENBAO_ADDR` | unset | Enables auto-unseal when set. |
| `OPENBAO_TOKEN` | unset | Token scoped to this SDK's own OpenBao path. |
| `OPENBAO_MOUNT` | `secret` | KV v2 mount point. |
| `OPENBAO_PATH_PREFIX` | `diagnos` | Prefix of the saved-state path. |
| `OPENBAO_NAMESPACE` | unset | OpenBao Enterprise namespace, if any. |
| `OPENBAO_TOKEN_FILE` | unset | A file holding the OpenBao token, read when `OPENBAO_TOKEN` is unset (what Kubernetes/Compose mount). |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` refuses to start if a secret cannot be locked in RAM. |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` skips disabling core dumps / `ptrace` at unlock (debugging only). |

Everything above can also be set explicitly, bypassing the environment
entirely: `Diagnos(settings=Settings(api_token="apikey-…", vault_url=..., time_precision="day"))`.

## What this SDK never does

- **Never sends a key to the vault.** Group DEKs, document DEKs, node
  keys, the SDK's own key pair — all of it is generated or opened locally
  and never leaves the process except sealed (enrollment) or, if you opt
  into auto-unseal, into OpenBao.
- **Never inspects a signed URL beyond using it.** A presigned `PUT`/`GET`
  URL from the vault is opaque; the SDK sends exactly the bytes and headers
  the protocol calls for and nothing more.
- **Never persists plaintext.** Decrypted records and file bytes exist
  only in the caller's own variables; the SDK itself keeps no cache, no
  temp-file copy of a completed download.
- **Never `repr`s a secret.** `Settings`, `ServiceAccountToken`,
  `SessionKeys`, `Keyring`, `Diagnos` itself — every `__repr__` in this
  codebase is redacted.
- **Never holds a key as a Python object.** Keys are `SecretBox`es in
  locked native memory (see "Where secrets live"); the only clear-text
  export is the OpenBao save you opt into, and even that zeroes its buffers
  the moment the request is built.

## A note on entropy

Every response to a signed request carries a `random_seed` in its JSON
envelope: 32 fresh bytes, sealed to this session, that this SDK mixes into
its own randomness before generating the next DEK, node key or nonce. It
never *replaces* `os.urandom` — a process that never received a seed still
gets ordinary OS randomness — it only adds a source the vault contributes
and a sibling process (say, two containers cloned from the same image,
booted before either re-seeded from hardware entropy) does not share. You
never configure this; it happens on every `Diagnos` instance automatically.

## Development

```sh
make sync                       # installs everything and builds the Rust enclave (needs cargo)
uv run --package diagnos pytest apps/sdk/tests
make lint                       # ruff, cargo fmt/clippy, docs
make types                      # mypy --strict
```

Run `make help` from the repository root for every target. Installing from
PyPI needs no Rust: wheels ship the compiled enclave for each platform
(abi3, CPython ≥ 3.11). Building from source needs a stable Rust toolchain
(`rustup`), which `uv sync` invokes through maturin.

See [`../README.md`](https://github.com/diagnos-tech/integration/blob/develop/README.md)
for the workspace layout and
[`docs/PROTOCOL.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.md)
for the normative wire contract this package implements.
