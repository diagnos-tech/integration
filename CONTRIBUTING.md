# Contributing

**English** · [Português (Brasil)](CONTRIBUTING.pt-BR.md)

Thank you for considering a contribution to `diagnos` — its base, SDK, CLI, API or wrappers. This document is the
practical guide: how to set up the project, the loop you run while working, what CI checks and how to reproduce
each check locally, the code conventions carried over from this repository's history, and the pull request
checklist. For the standards of behaviour we hold everyone to, see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). To
report a vulnerability, see [`SECURITY.md`](SECURITY.md) instead of opening an issue.

## Prerequisites

| You need | Why |
|---|---|
| [uv](https://docs.astral.sh/uv/) | one venv for the whole package, every extra installed editable |
| Python 3.11 – 3.13 | the three CPython versions CI tests against |
| [rustup](https://rustup.rs/) | only to build `apps/sdk/native` (the memory enclave) from source — it installs the Rust that `rust-toolchain.toml` pins; PyPI wheels ship prebuilt |

You do not need Rust installed to use `diagnos` from PyPI; you need it to build from a checkout, because `make sync`
compiles `apps/sdk/native` for you.

The code is one package, `src/diagnos`: the base (`_wrapper/`, `_entry.py`, `_extras.py`), the SDK at the top of the
package, `cli/` and `api/`. Each layer keeps its README, tests and assets under `apps/<layer>/`, and the base's under
`wrappers/py/`.

## First setup

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # installs every extra, editable, and builds the Rust enclave
make check   # lint + types + tests + contract check — what CI runs
```

If `make check` is green on a fresh clone, your environment matches CI's.

## The everyday loop

```sh
make fmt        # auto-format and auto-fix Python (ruff) and Rust (cargo fmt)
make test       # unit tests: every Python layer + the Rust enclave
make cov        # unit tests with one combined coverage report (htmlcov/)
make contract   # Pact consumer tests; regenerates contracts/*.json
```

Run `make help` at any time to list every target with a one-line description.

## What CI runs, and how to reproduce it locally

Pull requests target `develop`. CI runs on every pull request and its `CI` job is the one required check; Package
runs only on the release pull request from `develop` into `main`, where it decides whether `main` can be released.

| Workflow | Runs on | Answers | Local equivalent |
|---|---|---|---|
| `CI` (`.github/workflows/ci.yml`) | every pull request, pushes to `main`, weekly on `develop` | Do lint, `mypy --strict`, the docs, the Pact contract and every test pass — on CPython 3.11 and 3.13, with the coverage floor held? Are the workflows themselves safe (zizmor, actionlint)? | `make check`, `make cov`, `uvx zizmor .github/` |
| `Package` (`.github/workflows/package.yml`) | pull requests into `main`, releases | Do the seven wheels and the sdist build, does each wheel work installed alone on its platform — bare, then with every extra — and do both images build? | `uv build`, then `docker build --target api .` |
| `Release` (`.github/workflows/release.yml`) | `v*` tags on `main` | Signs and publishes everything; see [Releasing](#releasing). | — |
| `Auto-merge` (`.github/workflows/auto-merge.yml`) | Dependabot pull requests into `develop` | Queues minor and patch updates to merge once CI passes. | — |
| `Scorecard` (`.github/workflows/scorecard.yml`) | weekly | How the repository scores on supply-chain practices. | — |

`make check` runs `lint`, `types`, `test`, `contract-check` and `docs-check` — the steps of CI's jobs, in one command
— so a green `make check` on your machine means a green pull request.

## Code conventions

These rules govern code (`.py` and `.rs` files); they used to live in `CONVENTIONS.md`, which this document replaces.
Files under `.github/` are the exception to the bilingual rule below: their comments are in English only.

- **Bilingual docstrings.** Every module, class and public function carries a docstring with an English paragraph
  prefixed `🇺🇸` followed by the Portuguese paragraph prefixed `🇧🇷`. Inline comments follow the same pair on
  consecutive lines. Comments explain the **why** (the threat, the cost, the protocol constraint), never restate the
  code. Rust doc comments (`//!` for modules, `///` for items) follow the identical rule. `scripts/check_bilingual.py`
  (part of `make lint`) fails the build when a docstring or doc comment is missing either flag — everywhere in `src/`,
  and in tests for the module and every top-level test, fixture, helper and class.

  ```python no-run
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
- **`diagnos.cli` and `diagnos.api` import only `diagnos`.** If they need something the SDK does not expose, the SDK
  grows — the shells never reimplement cryptography, signing or retry logic.
- **The base needs nothing but the standard library.** `diagnos._wrapper`, `_entry`, `_extras` and the top of
  `diagnos/__init__.py` run on `pip install diagnos` alone: they never import the SDK, the CLI or the API, and a new
  public SDK name goes into both lists of `diagnos/__init__.py` (the `TYPE_CHECKING` imports and `_SDK`). The four
  base commands are a contract shared by every language wrapper (`wrappers/contract.json`) — change it there first.
- **Extras stay plain.** Every `Requires-Dist` of an extra is a plain `extra == "…"` marker, onto a distribution
  `wrappers/py/tests/test_extras.py` allows; a new one is a reviewed change to that list.
- **Pending decisions are `TODO(gustavo): ...`.** No `FIXME`, no `HACK`.
- **Secrets never live in a Python `bytearray` or `bytes`.** Session keys, DEKs and private keys live in
  `diagnos._secure.SecretBox` — page-locked Rust memory (`apps/sdk/native`), zeroed on drop. The only exit is `reveal()`,
  reserved for the OpenBao auto-unseal export.
- **`unsafe` Rust is confined.** It lives only in `native/src/locked/` (memory and capabilities),
  `native/src/buffer.rs` and `native/src/process.rs` (rlimit/prctl) — the places that actually touch raw memory.
  Every `unsafe` block carries a `SAFETY:` comment stating the invariant that makes it sound.
- **Frozen wire labels never get renamed.** The `imgexam-*-v1` HKDF/AAD labels (`src/diagnos/crypto/`) and the
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
(branch coverage, the whole package).

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

`develop` is where work lands; `main` holds what has been released or is about to be. `diagnos` and its two images
are released together, under one version, by `.github/workflows/release.yml`:

1. On `develop`, set the same version in `pyproject.toml` and `apps/sdk/native/Cargo.toml`, refresh both lockfiles
   (`uv lock` and `cargo update --workspace --manifest-path apps/sdk/native/Cargo.toml`), and give the version a date
   in `CHANGELOG.md` in place of `Unreleased`. `python3 scripts/release_version.py` says whether they agree.
2. Open a pull request from `develop` into `main`. Besides CI, it runs **Package**: every distribution built, each
   wheel tried on its platform, the sdist rebuilt and both images built — and nothing published. Merge it with a
   **merge commit**, never a squash, so `main` and `develop` keep one history.
3. Tag the merge commit as `v<version>` and push the tag: `git fetch origin && git tag v0.1.0 origin/main && git push
   origin v0.1.0`. **Release** runs Package again, signs every file with cosign and attests its provenance, pushes
   and signs the two images, waits for a maintainer to approve the `pypi` environment, publishes to PyPI and creates
   the GitHub release with every file, bundle and the commands that verify them.

A version on PyPI can never be uploaded twice, which is why Package runs on the pull request first. Publishing uses
PyPI [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) and Sigstore keyless signing: there is no token or
key to store or rotate — and an API token is deliberately not supported, because it would silently turn off the PEP
740 attestations. PyPI trusts `release.yml` in this repository, running in the `pypi` environment; renaming either
breaks publishing until PyPI's trusted publisher is changed to match. At runtime `__version__` is read from the
installed package's metadata rather than hard-coded.

Dependencies update themselves: Dependabot opens grouped pull requests into `develop` once a month, minor and patch
updates merge on their own once CI passes, and major updates wait for a review. They reach `main` with the next
release.

A release candidate rehearses everything for real: `0.1.0rc1` in `pyproject.toml`, `0.1.0-rc.1` in `Cargo.toml` (the
guard reads both as one version), a `## [0.1.0rc1]` section in `CHANGELOG.md`, and the tag `v0.1.0rc1`. `pip` installs
a pre-release only when asked for it by version or with `--pre`.

### Repository settings

What code cannot set, a repository admin does once — in this order, so PyPI never trusts an environment or a tag
anyone could use:

1. **Environments**: `release` and `pypi`, each limited to tags `v*`, with a required reviewer on `pypi` (and *Prevent
   self-review* off while there is one maintainer).
2. **Branches**: `main`, created from `develop`.
3. **Rulesets**:
   - tags `v*`: only maintainers create them (*Restrict creations*, bypassed by admins only), and nobody moves or
     deletes them (*Restrict updates* and *Restrict deletions*, no bypass — a second ruleset);
   - `develop`: pull requests only, the **CI** check required, no force pushes or deletions; require a code-owner
     review as soon as there are two maintainers;
   - `main`: pull requests only, the **CI** and **Package** checks required, merge commits only, no force pushes or
     deletions.
4. **General**: *Allow auto-merge* on (Dependabot needs it); under Actions, a read-only `GITHUB_TOKEN` and Actions not
   allowed to create or approve pull requests; release immutability on.
5. **PyPI**: a pending trusted publisher for `diagnos` — owner `diagnos-tech`, repository `integration`, workflow
   `release.yml`, environment `pypi` — and 2FA for every owner. Never an API token.
6. **GHCR**, during the first release: the run waits for approval before `pypi`, with both images already pushed and
   signed. Make `diagnos` and `diagnos-api` public and grant only this repository write access, *then* approve —
   `diagnos setup api` pulls the image as soon as the version is on PyPI.

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
