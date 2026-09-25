# Changelog

All notable changes to `diagnos`, `diagnos-cli` and `diagnos-api` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/). The three packages are versioned and released together.

This file is English-only and exempt from the repository's bilingual-documentation pairing rule
(`scripts/check_docs.py`).

## [0.1.0] - Unreleased

`0.1.0` is the first version of `diagnos`, `diagnos-cli` and `diagnos-api` ever published under these names — see
[`MIGRATING.md`](MIGRATING.md) if you are coming from an internal or from-source checkout of the former `imgexam`
monorepo.

### Added

- Renamed the project from `imgexam` to `diagnos`, end to end: packages (`imgexam` → `diagnos`, `imgexam-cli` →
  `diagnos-cli`, `imgexam-api` → `diagnos-api`), modules (`imgexam` → `diagnos`, `imgexam_cli` → `diagnos_cli`,
  `imgexam_api` → `diagnos_api`), the public class (`Imgexam` → `Diagnos`) and exceptions (`ImgexamError` →
  `DiagnosError`, `ImgexamPermissionError` → `DiagnosPermissionError`), every `IMGEXAM_*` environment variable to
  `DIAGNOS_*`, the CLI command (`imgexam` → `diagnos`), the Docker image (`imgexam-api` → `diagnos-api`), and the
  default vault URL to `https://vault.diagnos.health`. See [`MIGRATING.md`](MIGRATING.md) for the full list,
  including what was deliberately left unrenamed (the `imgexam-*-v1` cryptographic labels and the OpenBao static
  seal key id).
- Consumer-driven Pact contract test suite (`contracts/`) between the SDK and the vault: `make contract` /
  `make contract-check`, a deterministic, normalized `contracts/diagnos-sdk-diagnos-vault.json`, and provider states
  covering the clock, enrollment (pending, approved, denied, forgotten) and lock surface. See
  [`contracts/README.md`](contracts/README.md).
- `Makefile` as the single entry point for every check a contributor or CI runs (`sync`, `fmt`, `lint`, `types`,
  `test`, `cov`, `contract`, `contract-check`, `check`).
- Three GitHub Actions workflows: `CI` (static checks and `mypy --strict`), `Unit tests` (Python 3.11–3.13 plus the
  Rust enclave, with a coverage floor on every leg), and `Contract tests` (the Pact consumer suite, with a contract
  summary in the job log).
- A self-hosted coverage badge, published to the orphan `badges` branch from the `Unit tests` workflow.
- Bilingual (🇺🇸/🇧🇷) documentation across the repository, enforced by `scripts/check_docs.py` (every document ships
  as `NAME.md` + `NAME.pt-BR.md`) and `scripts/check_bilingual.py` (every module, class and public function's
  docstring, Python and Rust).

### Fixed

- `GET /time`: the SDK previously sent a `POST` with an id body and read nothing back, so clock sync failed before
  the first signed request; it now sends the `GET` the vault actually serves and reads the raw `{"result": <ms>}`
  response.
- The per-response entropy seed: the SDK read it from an `X-Session-Seed` header that the vault no longer sends; it
  is now read from `random_seed` in the JSON envelope of every signed response, where the vault actually puts it.
- `__version__` is now read from the installed package's metadata instead of being hard-coded, so the SDK reports
  its real version to the vault during enrollment.

### Known issues

- The document layer (`vault.patients`, `vault.exams`) and the drive/file layer (`vault.drives`) target an earlier
  revision of the vault's protocol and do not yet work against the current vault. See
  [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for exactly what changed and the plan to close the gap.
