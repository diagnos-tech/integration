# diagnos

**English** · [Português (Brasil)](README.pt-BR.md)

The official zero-knowledge Python SDK for the diagnos vault (`vault.diagnos.health`). Patients, exams and files are
encrypted in this process, in RAM, before a single byte reaches the network — the vault only ever sees ciphertext,
signed requests and presigned URLs. This package is the one place that complexity lives; `diagnos-cli` and
`diagnos-api` are thin shells over it.

> [!NOTE]
> **Status: 0.1.0 preview.** Enrollment, session keys, request signing, the clock, the lock, `vault.patients`,
> `vault.exams` and `vault.drives` speak the vault's current protocol and are verified against it by the Pact
> contract tests. Known limits:
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
pip install "diagnos[openbao]"          # with OpenBao auto-unseal, for servers
export DIAGNOS_API_TOKEN="apikey-…"     # issued by a workspace admin
```

> [!NOTE]
> Not on PyPI yet. Until the first release, install from source — building the enclave needs a
> [Rust toolchain](https://rustup.rs/):
> `pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"`

## Your first session

```python
from diagnos import Diagnos

vault = Diagnos()  # reads DIAGNOS_API_TOKEN; no network yet
vault.unlock()  # prints a link + a 6-digit code, waits for an admin to approve

for row in vault.patients.list():
    print(row.id, row.summary.display_name if row.summary else "—")
```

The token says *which* service account is asking; the approval decides what this process may decrypt. You rarely call
`unlock()` yourself — the first use of `vault.patients`, `vault.exams` or `vault.drives` unlocks lazily — and a
server that must restart without a person uses OpenBao auto-unseal, a deliberate trade the sessions guide spells out.

## What is inside

- **`vault.patients`, `vault.exams`** — versioned, sealed documents, readable and writable exactly as the web app
  reads and writes them, with typo-proof records and safe concurrent writes.
- **`vault.drives`** — files and folders under their own keys, uploaded in one `PUT` or in parts, downloaded as a
  stream.
- **A Rust memory enclave** — every key lives in locked memory, never swapped, never dumped, wiped on `fork()` and on
  drop, and never handed back to Python as `bytes`.
- **The protocol handled for you** — request signing, clock skew, retries of everything safe to retry, one exception
  class per decision you have to make.

## Guides

| Guide | |
|---|---|
| [Quickstart](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/quickstart.md) | token to first encrypted patient and file |
| [Concepts](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/concepts.md) | workspaces, groups, keys, versions, drafts, nodes |
| [Authentication](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/authentication.md) | the token, the enrollment link and code, the approval |
| [Sessions](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/sessions.md) | unlock, lock, expiry, OpenBao auto-unseal |
| [Patients](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/patients.md) · [Exams](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/exams.md) · [Files](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/files.md) | the three resources |
| [Errors](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/errors.md) | every exception, what is retried, clock skew |
| [Configuration](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/configuration.md) | every environment variable and `Settings` |
| [Security model](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/security.md) | what the vault sees, what the enclave protects |
| [SDK reference](https://github.com/diagnos-tech/integration/blob/develop/docs/reference/sdk.json) | every public class and function, generated from the code |

The enclave's own threat model is in [`native/README.md`](native/README.md), and the normative wire contract in
[PROTOCOL.md](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.md).

## Development

```sh
make sync                       # installs everything and builds the Rust enclave (needs cargo)
uv run --package diagnos pytest apps/sdk/tests
make lint                       # ruff, cargo fmt/clippy, docs
make types                      # mypy --strict
```

Run `make help` from the repository root for every target. Installing from PyPI needs no Rust: wheels ship the
compiled enclave for each platform (abi3, CPython ≥ 3.11). Building from source needs a stable Rust toolchain
(`rustup`), which `uv sync` invokes through maturin; after a Rust edit, `uv sync --reinstall-package diagnos`
rebuilds it.
