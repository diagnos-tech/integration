# Contributing

**English** · [Português (Brasil)](CONTRIBUTING.pt-BR.md)

Thank you for considering a contribution to `diagnos`, `diagnos-cli` or `diagnos-api`. This document is the
practical guide: how to set up the workspace, the loop you run while working, what CI checks and how to reproduce
each check locally, the code conventions carried over from this repository's history, and the pull request
checklist. For the standards of behaviour we hold everyone to, see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). To
report a vulnerability, see [`SECURITY.md`](SECURITY.md) instead of opening an issue.

## Prerequisites

| You need | Why |
|---|---|
| [uv](https://docs.astral.sh/uv/) | one venv for the whole workspace (`apps/sdk`, `apps/cli`, `apps/api`) |
| Python 3.11 – 3.13 | the three CPython versions CI tests against |
| [Rust](https://rustup.rs/) stable | only to build `apps/sdk/native` (the memory enclave) from source — PyPI wheels ship prebuilt |

You do not need Rust installed to use the packages from PyPI; you need it to build `diagnos` from a checkout, because
`make sync` compiles `apps/sdk/native` for you.

## First setup

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # installs everything and builds the Rust enclave
make check   # lint + types + tests + contract check — what CI runs
```

If `make check` is green on a fresh clone, your environment matches CI's.

## The everyday loop

```sh
make fmt        # auto-format and auto-fix Python (ruff) and Rust (cargo fmt)
make test       # unit tests: the three Python packages + the Rust enclave
make cov        # unit tests with one combined coverage report (htmlcov/)
make contract   # Pact consumer tests; regenerates contracts/*.json
```

Run `make help` at any time to list every target with a one-line description.

## What CI runs, and how to reproduce it locally

CI is three workflows, each answering one question. `make check` runs the same four steps in the same order, so a
green `make check` on your machine means a green PR.

| Workflow | Answers | Local equivalent |
|---|---|---|
| `CI` (`.github/workflows/ci.yml`) | Does the code pass static checks and type-check? | `make lint` (ruff, `cargo fmt --check`, `cargo clippy -D warnings`, bilingual-docstring check, docs-pairs/links check) + `make types` (`mypy --strict` over the packages, the contract tests and `scripts`) |
| `Unit tests` (`.github/workflows/unit-tests.yml`) | Do the three Python packages and the Rust enclave pass their own tests, on every supported CPython, without the coverage floor slipping? | `make cov` (or `make test` for a faster pass without the combined coverage report) |
| `Contract tests` (`.github/workflows/contract-tests.yml`) | Does the SDK still speak the HTTP contract the vault verifies? | `make contract-check` |

`make check` runs `lint`, `types`, `test` and `contract-check` in that order — it is exactly what the three workflows
run, just in one command on your machine.

## Code conventions

These rules govern code (`.py` and `.rs` files); they used to live in `CONVENTIONS.md`, which this document replaces.

- **Bilingual docstrings.** Every module, class and public function carries a docstring with an English paragraph
  prefixed `🇺🇸` followed by the Portuguese paragraph prefixed `🇧🇷`. Inline comments follow the same pair on
  consecutive lines. Comments explain the **why** (the threat, the cost, the protocol constraint), never restate the
  code. Rust doc comments (`//!` for modules, `///` for items) follow the identical rule. `scripts/check_bilingual.py`
  (part of `make lint`) fails the build when a docstring or doc comment is missing either flag — everywhere in `src/`,
  and in tests for the module and every top-level test, fixture, helper and class.

  ```python
  def sign(request: CanonicalRequest, sign_key: bytes) -> str:
      """🇺🇸 HMAC-SHA512 over the canonical string, hex-encoded.

      The vault reconstructs the same string from the raw request; any byte we
      normalize differently is a 401, so this mirrors `canonical.ts` verbatim.

      🇧🇷 HMAC-SHA512 sobre a string canônica, em hex.

      O cofre reconstrói a mesma string a partir da requisição crua; qualquer
      byte normalizado diferente é 401, então isto espelha `canonical.ts` ao pé
      da letra.
      """
  ```

- **Small files, one responsibility.** A folder per domain (`crypto/`, `session/`, `resources/`, `transport/`); a
  module that outgrows one responsibility becomes a package (`models/`, `resources/_documents/`). Aim for ~250 lines.
  `scripts/check_file_size.py` (part of `make lint`) fails the build above 300 lines for source and 500 for tests (a
  Rust file's inline `#[cfg(test)]` module does not count).
- **`cli` and `api` import only `diagnos`.** If they need something the SDK does not expose, the SDK grows — the
  shells never reimplement cryptography, signing or retry logic.
- **Pending decisions are `TODO(gustavo): ...`.** No `FIXME`, no `HACK`.
- **Secrets never live in a Python `bytearray` or `bytes`.** Session keys, DEKs and private keys live in
  `diagnos._secure.SecretBox` — page-locked Rust memory (`apps/sdk/native`), zeroed on drop. The only exit is `reveal()`,
  reserved for the OpenBao auto-unseal export.
- **`unsafe` Rust is confined.** It lives only in `native/src/locked/` (memory and capabilities),
  `native/src/buffer.rs` and `native/src/process.rs` (rlimit/prctl) — the places that actually touch raw memory.
  Every `unsafe` block carries a `SAFETY:` comment stating the invariant that makes it sound.
- **Frozen wire labels never get renamed.** The `imgexam-*-v1` HKDF/AAD labels (`apps/sdk/src/diagnos/crypto/`) and the
  OpenBao static seal key id `imgexam-static-v1` (`apps/api/deploy/`) are persisted cryptographic constants. Renaming one
  would make every stored ciphertext, or an existing OpenBao install, unreadable. See
  [`MIGRATING.md`](MIGRATING.md) for the full explanation.

## Documentation rule

Every document ships as `NAME.md` (English) next to `NAME.pt-BR.md` (Brazilian Portuguese), with a language switcher
right under the H1 linking to its sibling. `scripts/check_docs.py` (part of `make lint`) fails the build when a
document has no sibling, no switcher, or a dead relative link. `CHANGELOG.md` and the files under `.github/` are
exempt — see that script's docstring for the exact rule.

## Changing the HTTP behaviour of the SDK

If your change touches what `VaultTransport` sends to, or reads from, the vault, its contract has to change with it:

1. Add or update the interaction in `contracts/tests` (see [`contracts/README.md`](contracts/README.md) for how).
2. Run `make contract` to regenerate `contracts/diagnos-sdk-diagnos-vault.json`.
3. Commit the regenerated file in the same pull request.

CI's `make contract-check` fails a PR whose SDK behaviour changed without a matching contract change — it compares
the committed file against a fresh, full run instead of rewriting it.

## Coverage ratchet

`fail_under` in the root `pyproject.toml` (`[tool.coverage.report]`) is a floor, not a target: raise it when overall
coverage goes up, never lower it to make a pull request pass. `make cov` prints the current combined number
(branch coverage, all three packages).

To look at one area, keep the package-level source and read its rows: `pytest apps/sdk/tests --cov=diagnos
--cov-report=term-missing`. A dotted source such as `--cov=diagnos.crypto` makes coverage import the `diagnos`
package to locate it and then drop it from `sys.modules`; the Rust extension cannot be initialized twice, so it keeps
the first `CryptoError` as `SecureError`'s base while `diagnos.errors` is re-created — and every "wrong key must
raise `CryptoError`" test then fails. That is the measuring tool, not the enclave.

## Commit style

Commits follow [Conventional Commits](https://www.conventionalcommits.org/): a type, an optional scope, and an
imperative summary — for example `fix(sdk): correct clock skew handling`, `test(contracts): add a lock interaction`,
`docs: expand the OpenBao auto-unseal tradeoff`.

Every commit must carry a [DCO](https://developercertificate.org/) sign-off. Use `git commit -s` (or add
`Signed-off-by: Your Name <you@example.com>` by hand) on every commit; it certifies you have the right to submit the change under the project license.

## Releasing

Out of scope for this document. In short: there is no separate release process to follow yet — each package's
version lives in its own `pyproject.toml` (`apps/sdk/pyproject.toml`, `apps/cli/pyproject.toml`, `apps/api/pyproject.toml`), and at
runtime `__version__` is read from the installed package's metadata rather than hard-coded.

## Pull request checklist

Before you open a pull request:

- [ ] `make check` is green locally (lint, types, tests, contract check).
- [ ] If the SDK's HTTP behaviour changed, `contracts/diagnos-sdk-diagnos-vault.json` was regenerated (`make
      contract`) and committed.
- [ ] Any documentation you added or changed exists in both `NAME.md` and `NAME.pt-BR.md`, with matching structure
      and substance.
- [ ] New or changed public docstrings (Python and Rust) carry both the `🇺🇸` and `🇧🇷` paragraphs.
- [ ] No secrets, tokens or real credentials are committed — including in test fixtures and deploy examples.
- [ ] Commits follow Conventional Commits and are signed off (`git commit -s`).
