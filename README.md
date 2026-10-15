[![diagnos](https://diagnos.health/brand/svg/diagnos-lockup-gradient.svg)](https://diagnos.health)

# integration

**Zero-knowledge SDK, CLI and REST API for the diagnos vault.**

**English** · [Português (Brasil)](README.pt-BR.md)

[![CI](https://github.com/diagnos-tech/integration/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/diagnos-tech/integration/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdiagnos-tech%2Fintegration%2Fbadges%2Fcoverage.json)](https://github.com/diagnos-tech/integration/actions/workflows/ci.yml?query=branch%3Amain)
[![Package](https://github.com/diagnos-tech/integration/actions/workflows/package.yml/badge.svg)](https://github.com/diagnos-tech/integration/actions/workflows/package.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/diagnos-tech/integration/badge)](https://scorecard.dev/viewer/?uri=github.com/diagnos-tech/integration)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab)](pyproject.toml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-64748b)](LICENSE)

**[Install](docs/guides/install.md)** · **[SDK](apps/sdk/README.md)** · **[CLI](apps/cli/README.md)** ·
**[API](apps/api/README.md)** · [Wrappers](wrappers/README.md) · [Protocol](docs/PROTOCOL.md) ·
[Contract tests](contracts/README.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

One open-source Python package, `diagnos`, for talking to the diagnos vault without ever handling a signed URL, an
HMAC or a key envelope yourself. Everything clinical is encrypted **inside your process** before it touches the network — the
vault only ever sees ciphertext. This package makes that the *easy* path.

> [!NOTE]
> **Status: 0.2.0 preview.** Every surface — enrollment, sessions, request signing, patients, exams, files and
> folders — speaks the vault's current protocol and is verified against it by the [contract tests](contracts/README.md).
> Known limits, and the questions still open on the vault side, are in [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## Install what you need

| Install | You get | Use it when |
|---|---|---|
| `pip install diagnos` | `diagnos docs`, `version`, `setup`, `help` — no dependencies | a first look; it installs the rest for you |
| `pip install "diagnos[sdk]"` | [the SDK](apps/sdk/README.md) — `from diagnos import Diagnos` | your code is Python |
| `pip install "diagnos[cli]"` | [the CLI](apps/cli/README.md) — `diagnos login`, `diagnos patients list`, … | scripts, operations, a quick look |
| `pip install "diagnos[api]"` | [the REST API](apps/api/README.md) — `diagnos-api`, or its signed image | your system speaks HTTP, not Python |

Same credential, same approval flow, same guarantees: the CLI and the API are thin shells over the SDK — they never
reimplement a single byte of cryptography. One package carries all three; an extra only adds a layer's
dependencies. Or let the base do it, step by step:

```sh
uv tool install diagnos   # or: pipx install diagnos
diagnos setup sdk         # the SDK in the Python project here, with uv
diagnos setup cli         # every command for this `diagnos`, with uv
diagnos setup api         # the API image, pulled and verified by digest, with Docker and cosign
```

Every release is signed with Sigstore and carries build provenance — [verify it](SECURITY.md#verifying-a-release).
Developers in other languages get the same four base commands through [wrappers](wrappers/README.md).

> [!NOTE]
> Until `0.2.0` is on PyPI, install from source — [Install](docs/guides/install.md) has the commands, and the
> [Rust toolchain](https://rustup.rs/) the build needs.

## Quick start

**1. Get a credential.** A workspace admin opens *Settings → Service accounts* in the diagnos web app, creates a
service account and copies its credential — shown once, because the vault keeps only the public half of the key:

```sh
export DIAGNOS_CREDENTIAL="svc_<32 hex>@<workspace_id>.diagnos.health:<key>"
```

> [!NOTE]
> The `apikey-` token in `DIAGNOS_API_TOKEN` is deprecated: it works, with a warning, until **2027-04-15**.
> [MIGRATING.md](MIGRATING.md#from-the-apikey--token-to-a-service-account-credential-020) swaps it in three steps.

**2. Enroll.** The first run prints a link and a 6-digit code; an admin approves it in the web app and picks which
security groups this process may read.

```python
from diagnos import Diagnos

with Diagnos() as vault:  # enrolls on entry: prints the approval link + code
    print(vault.workspace_id)
    print(vault.security_groups)  # the groups the admin granted
```

```sh
diagnos login          # the same enrollment, from the terminal — kept for the next commands
diagnos patients list  # reuses it, no new approval
diagnos logout         # revokes it and wipes the keys
```

**3. Use it.** Patients, exams and files hang off the same object — `vault.patients`, `vault.exams`,
`vault.drives`. The [quickstart](docs/guides/quickstart.md) goes from here to your first encrypted patient and file, and
[`examples/`](examples/README.md) has complete programs to copy: upload a file, patients, exams, error handling.

One name, three spellings: a **security group** is `security_group=` in the SDK (`security_group_id` on what it
returns), `--group` / `DIAGNOS_GROUP` in the CLI, and `security_group` or `{sg}` in the API.

Private keys never leave the process and nothing is written to disk, so a new process needs a new approval — that is
the design, not a limitation. The CLI keeps its session in one background process between `login` and `logout`.
[Authentication](docs/guides/authentication.md) shows the credential and the whole enrollment, and
[Sessions](docs/guides/sessions.md#auto-unseal-with-openbao) how servers restart without a human.

## What you get for free

- **🔐 End-to-end by default** — records and files are encrypted in your process; the vault sees ciphertext, signed
  requests and presigned URLs. [Exactly what it sees](docs/guides/security.md#what-the-vault-sees).
- **🛡️ Post-quantum hybrid** — enrollment uses X25519 + ML-KEM-768, so a recorded session stays safe against a future
  quantum adversary.
- **🧱 Keys in a Rust enclave** — `mlock`ed memory, guard pages, excluded from core dumps, zeroed on `fork()` and on
  drop, never handed back to Python as `bytes`. Threat model: [`apps/sdk/native/README.md`](apps/sdk/native/README.md).
- **🔁 Retries and clock skew handled** — idempotent retries, clock sync with the vault, stable exceptions:
  [Errors](docs/guides/errors.md).
- **📐 Pinned byte formats** — [`docs/PROTOCOL.md`](docs/PROTOCOL.md) is normative, and test vectors generated from
  the vault's reference implementation pin every byte.

## Servers without a human

A human approval on every restart is fine for a laptop; it is not fine for a Kubernetes pod. Point the SDK at
[OpenBao](https://openbao.org/) and it saves its unlocked session right after enrollment and restores it on every
start — a deliberate trade, [explained in full](docs/guides/sessions.md#auto-unseal-with-openbao) before you turn it
on. Ready-made manifests live in [`apps/api/deploy/`](apps/api/deploy/README.md): Docker Compose and Kubernetes, with
OpenBao auto-unseal for AWS KMS, Azure Key Vault, GCP KMS, Transit, Shamir and static keys.

## Documentation

| Start here | Then |
|---|---|
| [Quickstart](docs/guides/quickstart.md) · [Install](docs/guides/install.md) · [Concepts](docs/guides/concepts.md) | [Authentication](docs/guides/authentication.md) · [Sessions](docs/guides/sessions.md) · [Configuration](docs/guides/configuration.md) |
| [Patients](docs/guides/patients.md) · [Exams](docs/guides/exams.md) · [Files](docs/guides/files.md) · [Examples](examples/README.md) | [Errors](docs/guides/errors.md) · [Security model](docs/guides/security.md) |
| [CLI guide](docs/guides/cli.md) · [REST API guide](docs/guides/api.md) | [Deploying](apps/api/deploy/README.md) · [Protocol](docs/PROTOCOL.md) · [Compatibility](docs/COMPATIBILITY.md) |

The developer site publishes these same pages at `/dev/docs`, plus a reference generated from the code — every
command, route and class. [How the docs are built and checked](docs/README.md).

## Quality gates

Every badge above is a workflow or what one measures; all but the last two run locally with one command.

| Badge | What it proves | Locally |
|---|---|---|
| **CI** | every layer — base, SDK, CLI, API — passes its tests on CPython 3.11 and 3.13, plus the Rust enclave; lint (Python, Rust, bilingual docstrings, docs), `mypy --strict`, the lockfile, the docs (every example runs, the reference is fresh), the [Pact](https://pact.io) contract the vault verifies, and the workflows themselves (zizmor, actionlint) | `make check` |
| **Coverage** | combined branch coverage of the whole `diagnos` package, with a floor that only goes up | `make cov` |
| **Package** | all seven wheels and the sdist build, and each wheel works installed alone on its platform — bare, then with every extra; both images build | `uv build` |
| **OpenSSF Scorecard** | the supply-chain practices: pinned dependencies, least-privilege tokens, signed releases, branch protection | — |

Releases are cut from `main` by [`release.yml`](.github/workflows/release.yml): Sigstore signatures and SLSA
provenance on every file and image, an SBOM, PyPI through Trusted Publishing — no long-lived secret anywhere. CodeQL
analyzes every pull request, and libFuzzer exercises the enclave's parsers every week.

The contract is consumer-driven: the SDK's tests write
[`contracts/diagnos-sdk-diagnos-vault.json`](contracts/diagnos-sdk-diagnos-vault.json), and the vault verifies that
same file against its real code before it deploys.

```mermaid
flowchart LR
    SDK["SDK tests<br/>(Pact mock, Rust engine)"] -->|write| C[("diagnos-sdk-diagnos-vault.json")]
    C -->|replayed against| V["vault.diagnos.health<br/>provider verification"]
```

## Repository layout

```
integration/
├── src/diagnos/       diagnos          the one package — `pip install diagnos[…]`
│   ├── _wrapper/      (base)           docs · version · setup · help, standard library only
│   ├── …              [sdk]            the SDK: client, crypto, session, transport, resources, models
│   ├── cli/           [cli]            `diagnos …` in your terminal
│   └── api/           [api]            REST facade (FastAPI), mTLS only
├── apps/              (per layer)      each layer's guide, tests and assets
│   ├── sdk/native/    diagnos._secure  Rust memory enclave
│   └── api/deploy/    compose · k8s    ready-to-run manifests
├── wrappers/          contract.json    the four base commands, for every language · py/: the Python one
├── examples/          NN-name/main.py  complete, runnable programs for the SDK
├── contracts/         Pact             consumer contract with the vault + its tests
├── docs/              guides/          the documentation · reference/ generated from the code
│                      PROTOCOL.md      normative byte formats · COMPATIBILITY.md · site.json
├── scripts/           docs/            the checks behind `make lint`, `make docs-check` and CI
└── Dockerfile         api · cli        the two images, built from the wheel
```

## Contributing

You need [uv](https://docs.astral.sh/uv/), Python 3.11–3.13 and, to build the enclave from source,
[rustup](https://rustup.rs/) — it installs the Rust that `rust-toolchain.toml` pins.

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # installs every extra, editable, and builds the Rust enclave
make check   # exactly what CI runs: lint, types, unit and contract tests, docs
make         # lists every other target
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before your first pull request. Coming from the `imgexam` packages? See
[MIGRATING.md](MIGRATING.md).

## Security

Found a vulnerability? Please **do not** open a public issue — report it privately through
[GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new). Details in
[SECURITY.md](SECURITY.md).

---

[Apache-2.0](LICENSE) · [diagnos.health](https://diagnos.health)
