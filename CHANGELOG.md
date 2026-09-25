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
- Repository layout: the three packages live under `apps/` (`apps/sdk`, `apps/cli`, `apps/api`); `contracts/`,
  `docs/` and `scripts/` stay at the root.
- `update(..., expected_latest_version_id=...)` (CLI `--expect-version`): the vault refuses the write if another
  version was saved since. Reservations that meet another writer's pending version are retried briefly (1.5 s, 3 s),
  and commits lost to the network or a `5xx` are replayed with backoff.
- Patient `tags` (sealed list labels): `create(..., tags=[...])`, `update(..., tags=...)` (`None` keeps them), CLI
  `--tag`.
- `DIAGNOS_TIME_PRECISION` / `Settings.time_precision`: truncate dates to the workspace's anonymization precision
  before sealing, as the web app does; `diagnos.truncate_timestamp` and `diagnos.to_iso_instant` for your own dates.
- `ProtocolError` for a vault answer the protocol does not allow (e.g. a signed size that is not the body's).

### Changed

- **Patients and exams speak the vault's current protocol** (`vault.patients`, `vault.exams`, and the matching CLI
  commands and API routes). A document belongs to exactly one security group (`security_group=` takes one id;
  `DocumentIndex.security_group_id`); version state lives in `DocumentIndex.streams` (with `latest_version_id`,
  `versions` and `pending_version_id` shorthands for the `data` stream); patients' version routes carry
  `/streams/data`; every version is sealed under a per-version key derived from the vault's `security_context`, as a
  raw `salt ‖ nonce ‖ ciphertext` body; every write carries the sealed summary (`encrypted_index`). Pinned by vectors
  sealed with the web app's own code and by 13 new contract interactions.
- `PatientRecord` and `ExamRecord` now mirror the web app's records: `identifiers` (vault-sealed), `address`,
  `race_identity`; `report_lexical`/`report_html`, `modality`, `exam_date`. `legal_id`, `ExamRecord.description` and
  `ExamRecord.report` are gone. Dates are stored the way the web app stores them (UTC ISO 8601 instants).
- A misspelled record field (`birthdate`) is refused with the field it resembles; any other unknown field is kept, so
  a read-modify-write never drops a field the web app added. Validation errors on records never echo the value.
- `list()` returns rows with the decrypted summary (`PatientListItem`/`ExamListItem`); the CLI shows it with
  `--summary` and the API with `?summary=true` — rows stay anonymous by default.
- `get()` returns the newest content like the web app (a newer draft wins); `include_draft=False` / `--committed`
  read committed versions only.
- Archive and delete no longer re-upload the record: they are flag changes without a new version. New `restore()`
  (CLI `restore`, API `POST …/restore`) takes a document out of the trash.
- `Exams.create` no longer takes `modality=`: modality is a sealed record field; only `patient_id` is sent in clear.

### Fixed

- CLI: decrypted fields, file names, vault-issued ids and the approval URL are printed literally instead of being
  parsed as `rich` markup (a `[html]` label disappeared; a record could restyle the terminal).
- API: `404` on an unknown route and `405` on a wrong method now answer with the uniform
  `{"error": {code, message, trace_id}}` envelope.
- Docker image: the build context's ignore file is at the repository root (the one under `api/` was never read, so
  local `.venv`/`target/` could reach the build), and uv is pinned to a version that reads the current `uv.lock`.
- `GET /time`: the SDK previously sent a `POST` with an id body and read nothing back, so clock sync failed before
  the first signed request; it now sends the `GET` the vault actually serves and reads the raw `{"result": <ms>}`
  response.
- The per-response entropy seed: the SDK read it from an `X-Session-Seed` header that the vault no longer sends; it
  is now read from `random_seed` in the JSON envelope of every signed response, where the vault actually puts it.
- `__version__` is now read from the installed package's metadata instead of being hard-coded, so the SDK reports
  its real version to the vault during enrollment.

### Known issues

- The drive/file layer (`vault.drives`) targets an earlier revision of the vault's protocol and does not yet work
  against the current vault. See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for exactly what changed and the
  plan to close the gap.
