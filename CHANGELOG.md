# Changelog

All notable changes to `diagnos` — the package, its extras and its images — are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/). The package and its two images are versioned and released together.

This file is English-only and exempt from the repository's bilingual-documentation pairing rule
(`scripts/check_docs.py`).

## [0.2.0] - 2026-10-15

`0.2.0` replaces the service account's `apikey-` token with a **service account credential**: an Ed25519 key whose
identity reads like an e-mail address, `svc_<hex>@<workspace_id>.diagnos.health`, and which signs every request
instead of sending a reusable bearer. The `apikey-` token keeps working, with a deprecation warning, until the vault
stops accepting it on **2027-04-15** — [`MIGRATING.md`](MIGRATING.md#from-the-apikey--token-to-a-service-account-credential-020)
has the three-step migration.

### Added

- **Service account credential.** `DIAGNOS_CREDENTIAL="svc_<hex>@<workspace_id>.diagnos.health:<key>"` (one line,
  copied once from the service account page), or `DIAGNOS_CREDENTIALS_FILE` pointing at the JSON downloaded at
  creation, or that file saved as `~/.config/diagnos/credentials.json` — read in this order. The private key (a
  32-byte Ed25519 seed) moves into the Rust enclave the moment it is parsed and never reaches the Python heap again;
  `repr`/`str` mask the identity and never show the key, and the credential refuses to be pickled. A credential
  file readable by other users still loads, with a warning to `chmod 600` it.
- **Signed requests (RFC 9421).** Every request to `/api/external/v1` carries `Signature-Input`, `Signature` (Ed25519
  over `@method`, `@path`, `@query` when there is one, `content-digest` when there is a body, `created`, a 16-byte
  `nonce`, the full identity as `keyid`, `alg="ed25519"`) and, with a body, `Content-Digest` (RFC 9530). No
  `Authorization` header is sent. Every attempt — retries included — gets a fresh nonce. The session HMAC
  (`X-Signature-*`) is unchanged and still rides on every session route.
- `ServiceAccountCredential` (`parse`, `from_file`, `from_env`, `identity`, `key_id`, `workspace_id`,
  `service_account`, `public_key`), `Diagnos(credential=…)` (the credential, its one-line form or the path of its
  file) and `Diagnos.from_env(env=None, **options)`; `Settings.credential` and `Settings.from_env(credential=…)`.
- `Diagnos.identity` and `Diagnos.credential_kind` (`"ed25519"` or `"legacy_apikey"`).
- Typed errors for every credential failure, each one saying exactly what to do: `CredentialError` (catch-all),
  `CredentialSignatureError`, `CredentialReplayError`, `ClockSkewError` (with `skew_seconds` and `server_time`,
  read from the error's `server_time` or the response's `Date`, and printed as "N s ahead/behind the vault"),
  `CredentialRevokedError`, `CredentialExpiredError`, `CredentialUnknownError` (all `AuthenticationError`),
  `WorkspaceMismatchError` and `ScopeMissingError` (with `permission` and `security_group_id`; both
  `DiagnosPermissionError`). `VaultError.details` carries the error's recovery data.
- The enclave signs Ed25519 (`ed25519-dalek`, the same dalek family as its X25519), checked against the RFC 8032
  vectors and RFC 9421 Appendix B.2.6.
- cargo-fuzz targets for the enclave's AEAD, secretstream and hybrid-seal parsers, run weekly (`make fuzz` locally).
- CodeQL analysis of the Python package, the Rust enclave and the workflows on every pull request.
- Every release carries its SLSA provenance (`diagnos-<version>.intoto.jsonl`) and a signed CycloneDX SBOM of its
  Python dependencies (`diagnos-<version>.cdx.json`).

### Changed

- `Diagnos.account_id` is `None` with a service account credential (its identity is the key itself); the REST API's
  `GET /v1/session` returns `account_id: null` in that case. With OpenBao auto-unseal, a credential's session is
  kept at `<prefix>/<workspace_id>/<key_id>`.
- A `credential_clock_skew` answer re-syncs the clock against `GET /time` and retries once, like
  `SignatureTimestampSkew`; `credential_replayed` is never retried, because the first copy may have gone through.
- The contract (`contracts/diagnos-sdk-diagnos-vault.json`) now describes the credential's headers on every
  interaction, keeps three interactions on the legacy token, and adds a revoked-key registration.
- The PyPI summary is now "SDK, CLI & API to integrate with diagnos.health".
- Releases: `main` is fast-forwarded to the `develop` commit being released, never merged into, so both branches keep
  one linear history; Package runs on that push.

### Deprecated

- `DIAGNOS_API_TOKEN` / `Diagnos(token=…)` / `--token` (`apikey-<jwt>`): still accepted, with a
  `LegacyTokenWarning` (a `DeprecationWarning`, attributed to the caller's line) and one log line per process. The
  vault stops accepting the token on 2027-04-15.

### Fixed

- The Rust enclave's secretstream panicked (a `PanicException` in Python) on associated data longer than 16 bytes,
  instead of authenticating it: the padding arithmetic underflowed. Found by the new fuzz targets. The SDK's own file
  encryption passes no associated data and was not affected.

## [0.1.0] - 2026-10-13

`0.1.0` is the first version of `diagnos` ever published — see
[`MIGRATING.md`](MIGRATING.md) if you are coming from an internal or from-source checkout of the former `imgexam`
monorepo.

### Added

- **One package, `diagnos`, with extras.** `pip install diagnos` is the base: no dependencies at all, and four
  commands — `diagnos docs` (Help Center, Developer Central, Trust Center), `diagnos version` (version, interpreter,
  platform and installed extras, `--json` too), `diagnos setup` and `diagnos help`. `diagnos[sdk]` adds the SDK
  (`from diagnos import Diagnos`), `diagnos[cli]` the full command line, `diagnos[api]` the REST API (`diagnos-api`);
  `openbao` and `dev-certs` sit on top. `import diagnos` works on the base install, and a missing extra raises
  `MissingExtraError` naming the command that adds it. `diagnos-cli` and `diagnos-api` are no longer separate
  packages; [`MIGRATING.md`](MIGRATING.md) maps the old names.
- `diagnos setup sdk | cli | api`: installs one layer step by step — the SDK into your project with `uv add`, the CLI
  into the environment that runs `diagnos` (or as a `uv tool`), the API as its signed image with Docker. Every
  command is shown first and confirmed once (default no); `--dry-run` and `--yes` for scripts. The API image is
  verified by the pulled digest with cosign (3.1.3+) against the release workflow's identity, and the `docker run` is
  printed by that digest. A missing `uv` or Docker exits with `69` and its install page — nothing is ever installed
  behind your back.
- `wrappers/contract.json`: the language-neutral contract of the four base commands, for wrappers in other
  languages; the Python base is tested against it.
- Signed releases: every wheel, the sdist and `SHA256SUMS` carry a cosign keyless signature and a SLSA provenance
  attestation; PyPI gets PEP 740 attestations through Trusted Publishing; the GitHub release attaches every file,
  bundle and the commands that verify them ([`SECURITY.md`](SECURITY.md#verifying-a-release)).
- Images on GHCR, for `linux/amd64` and `linux/arm64`: `ghcr.io/diagnos-tech/diagnos-api` and
  `ghcr.io/diagnos-tech/diagnos` (the CLI), built from the released wheels, with SBOM and provenance, signed by
  digest. They run as uid `10001` with root-owned, read-only code and no pip or uv.

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
  covering the clock, enrollment (pending, approved, denied, forgotten), lock, patients, exams and files. See
  [`contracts/README.md`](contracts/README.md).
- `Makefile` as the single entry point for every check a contributor or CI runs (`sync`, `fmt`, `lint`, `types`,
  `test`, `cov`, `contract`, `contract-check`, `check`).
- GitHub Actions: `CI` on every pull request (lint, `mypy --strict`, the docs, the Pact contract, the Rust enclave,
  every Python suite on CPython 3.11 and 3.13 with a coverage floor, and zizmor and actionlint over the workflows),
  behind one required check; `Package` on pull requests into `main`; `Release` on `v*` tags on `main`; monthly
  grouped Dependabot updates into `develop`, whose minor and patch updates merge on their own once CI passes; and a
  weekly OpenSSF Scorecard.
- A self-hosted coverage badge, published to the orphan `badges` branch by `CI` on every release.
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
- `ProtocolError` for a vault answer the protocol does not allow (e.g. a signed size that is not the body's); the API
  answers it with `502` and `code: protocol_error`.
- Folders: `Drive.create_folder()`, and `parent_id=` on `upload`, `upload_many`, `list` and `iter_all` (CLI
  `files mkdir` and `--folder`; API `POST /v1/drives/{sg}/folders` and `parent_id`).
- Workspace-wide files: `vault.drives.list()`/`iter_all()` across every group the session may list, filtered by
  `security_group`, `exam_id`, `parent_id` and `include_pending`; `vault.drives.get()`, `name_of()`, `download()` and
  `iter_download()` read any file by node id alone (CLI `files list` without `--group`, `files get`/`download` by id).
- `DIAGNOS_STORAGE_HOSTS` / `Settings.storage_hosts`: presigned storage URLs are followed only over HTTPS to an
  allowed host or its subdomains — by default the user-content domain `diagnosusercontent.com` and R2's
  `r2.cloudflarestorage.com` — so ciphertext and SSE-C keys never go to a host nobody chose.
- CLI: `--group` is optional on `patients create`, `exams create`, `files upload` and `files mkdir` — it falls back to
  `DIAGNOS_GROUP`, then (for an exam) the patient's group, then the session's only group, and says which it picked;
  with several groups it stops and lists them.
- `Patients.index(id)` / `Exams.index(id)`: a document's metadata (group, versions, flags) without opening its record.
- CLI session agent: `diagnos login` keeps the session for the commands that follow, until `diagnos logout`, the idle
  timeout (`DIAGNOS_AGENT_IDLE_MINUTES`, 8 hours by default) or `SIGTERM`. The session stays in one background
  process, in the SDK's locked memory; later commands send it their arguments over a private Unix socket and it runs
  them, streaming output, prompts and exit codes back — the keys never leave that process, nothing is written to disk
  and no OS keychain is used. `DIAGNOS_AGENT=off` keeps every command in its own process. `diagnos status` shows the
  agent.
- CLI `diagnos logout`: revokes the kept session, wipes its keys and stops the agent.
- CLI global options (`--json`, `--quiet`, `--no-color`, `--token`, `--vault-url`) go anywhere on the line:
  `diagnos patients list --json` works.
- API `diagnos-api dev-certs [DIR]`: a throwaway local CA, a `localhost` server pair and a client pair in one step
  (keys `0600`, 30 days, never overwritten without `--force`; needs the `diagnos[dev-certs]` extra outside a
  checkout). `python -m diagnos.api` runs the API like `diagnos-api`.
- `diagnos.UploadSource`, exported at the top level. A `.dcm` file is typed `application/dicom`, so the vault
  classifies it.

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
- **Files speak the vault's current protocol** (`vault.drives`, CLI `files`, API `/v1/drives`): the `/nodes` routes;
  a DEK per file or folder, wrapped for its group (`imgexam-node-dek-v1`); the name sealed under it
  (`imgexam-node-name-v1`); a content key derived from the vault's `security_context`; the web app's SSE-C key (the
  content key's sister) on the `PUT`, on every multipart part and on the `GET`; up to 100 files per reservation, with
  an idempotency `client_ref` each; multipart parts signed in waves of up to 200 and aborted on failure. Pinned by
  vectors generated with the web app's upload code and by 5 new contract interactions.
- The secretstream framing now always ends with its own `FINAL` frame (empty when the size is an exact multiple of
  1 MiB), as the web app writes it; `encrypted_size()` follows.
- `DriveNode` mirrors the vault's node (`kind`, `parent_id`, `encrypted_name`, `encrypted_keys`, `media_kind`,
  `optimized_variants`, …); `StagedNode` replaces `UploadedNode`.
- `upload()` of `bytes` or an anonymous stream requires `name=`: every node carries a sealed name.
- An upload confirmed as `missing` raises `ConflictError` with code `UploadIncomplete`.
- API: a node read under another group's `{sg}` answers `404`; `limit` is bounded to 1–200.
- A missing group key (`GroupKeyUnavailable`) is a permission error: API `403` with `code: group_key_unavailable`
  (was a generic `500`), CLI exit code `3`. Listings degrade instead of failing: a file whose group key the session
  lacks is listed with `name: null` (CLI: 🔒), like document summaries.
- CLI `files … --json` prints `{node, name}` per file, the same shape as the API.
- CLI: `--file` together with inline record flags (`--legal-name`, `--title`, …) is a usage error naming the flags;
  the flags used to be dropped without a word. `--file -` reads the record from stdin.
- CLI: a bare `diagnos` prints the help with where to start and exits `0` (was `2`).

### Removed

- `DIAGNOS_SSE_C` and `Settings.sse_c`: files always use SSE-C exactly as the web app does, and documents never do,
  so there is nothing left to choose.

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
- CLI `files download` without `-o` writes to the last segment of the decrypted name only: the web app stores a
  relative path there, and a name such as `../../.bashrc` could otherwise write outside the working directory. The
  API's `Content-Disposition` offers the same base name.
- Contract harness: running with `-p no:cacheprovider` no longer crashes the partial-run check.
- CLI: a local file problem (an `-o` into a directory that does not exist, an unreadable upload) prints
  `I/O error` and exits `1` instead of a Python traceback.
- CLI: `--no-color` and `NO_COLOR` drop every ANSI escape, bold and dim included, not only colors.
- API: `/openapi.json` and `/docs` require the client certificate like every other route (FastAPI mounts its own
  schema routes outside the app's dependencies); `/redoc` is gone.

### Known issues

- Multipart uploads (files above 64 MiB) are covered by unit tests, not by the contract: the vault's provider
  verification has no S3 endpoint for R2. Whether R2 accepts SSE-C on those parts is one of the questions still open
  on the vault side — see [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).
