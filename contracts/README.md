# Contract testing · SDK ↔ vault

**English** · [Português (Brasil)](README.pt-BR.md)

This is the contract-testing suite between the `diagnos` SDK (the consumer) and the vault (the provider). It runs
the real SDK against a local Pact mock server and records exactly the HTTP the SDK sent and expected, as
`diagnos-sdk-diagnos-vault.json` — the file the vault's own CI replays and verifies before it deploys.

## What consumer-driven contract testing is

In a consumer-driven contract, the *consumer* of an API (here, the SDK) writes tests that exercise its real client
code against a mock of the *provider* (the vault), and those tests generate a contract file describing every
interaction: the request the consumer sends and the response shape it needs back. The provider then replays that
same file against its real implementation ("provider verification") to prove it satisfies every consumer that
depends on it. The contract is generated from consumer tests, not hand-written — that is what "consumer-driven"
means, and it is why it cannot drift from what the SDK actually does: the file is a byproduct of tests that fail if
the SDK's real behaviour disagrees with it.

## What this suite proves, and what it doesn't

- **This suite proves**: the SDK sends exactly the requests `diagnos-sdk-diagnos-vault.json` describes, and reads
  successfully from exactly the responses it describes. Every test in `contracts/tests` drives real SDK code
  (`VaultTransport`, `enroll()`, `SessionManager.lock()`) against the Pact mock server, which fails the test if the
  SDK sends a request no interaction describes, or if an interaction is never exercised.
- **This suite does not prove**: that the vault actually behaves this way. That half — "provider verification" —
  runs in the vault's own (private) repository, which vendors this contract file and replays it against a real
  vault, with a provider state handler that seeds the data each interaction's `providerStates` name requires. If
  the vault's behaviour and this contract disagree, provider verification fails there, not here.
- There is **no Pact broker** in this setup. The contract travels as a committed JSON file
  (`contracts/diagnos-sdk-diagnos-vault.json`), not through a broker service; the vault's repository takes it by
  vendoring this one (directly, or via whatever mechanism that repository documents).

## How to run it

```sh
make contract         # runs the suite; on a full, passing run, regenerates the committed contract
make contract-check   # runs the suite and fails if the regenerated contract differs from the committed one
```

`make contract` is what you run after changing the SDK's HTTP behaviour or adding an interaction, before committing.
`make contract-check` is what CI runs (`.github/workflows/contract-tests.yml`) — it never rewrites the file, only
compares.

## How determinism works

A Pact file records the concrete *examples* each interaction was defined with, not just their shape — and several
of those examples (a sealed session, a sealed group key, a `random_seed`) are real ciphertext the SDK has to
actually decrypt. If that ciphertext were produced with real randomness, the contract file would change on every
run even though nothing about the SDK's behaviour changed. Three things keep it stable:

1. **Fixed-label crypto oracles** (`contracts/tests/_crypto.py`). Every random input the protocol normally draws
   (ephemeral X25519 secret, ML-KEM encapsulation coin, HKDF salt, AES-GCM nonce) is derived deterministically from
   a fixed string label with SHA-256 (`fixed_bytes(label)`), using independent implementations (`pynacl`,
   `kyber-py`, `cryptography` — not the SDK's own Rust enclave) so a passing contract test also cross-checks the
   enclave against a second implementation of the wire format. **This is a test oracle, never a pattern to copy**:
   reusing a nonce under a real key in production code is exactly what the SDK is built to never do.
2. **Normalization** (`contracts/tests/conftest.py::normalize`). The raw Pact output includes tool metadata
   (`metadata.pactRust`, which `pact_ffi` build wrote the file) and interactions in whatever order tests happened to
   run. Normalization drops the tool metadata and sorts interactions by `(description, providerStates)`, so the
   committed file is a pure function of the interactions themselves — a dependency bump or a reordered test file
   never produces a diff.
3. **Partial runs never rewrite the file.** `pytest_sessionfinish` only writes (or, under `--contract-check`,
   compares) when the run was the full suite and every test passed (`_is_partial_run` checks for `-k`, `-m`,
   `--lf`, or a narrowed path). Run one file or one `-k` expression while developing without fear of clobbering the
   committed contract with a partial view of it.

## Matchers vs. literals: the two rules

Straight from `_wire.py`'s module docstring, because they are the whole point of a consumer-driven contract:

1. **Only what the SDK reads goes into a response.** The vault may send more — Pact allows extra keys in a response
   body — but the contract pins exactly what the SDK would break without, nothing it merely tolerates.
2. **A value is literal when the SDK branches on it, a matcher when only its shape matters.** `"status": "approved"`,
   `"mode": "single"`, `"success": true` are literal — a renamed enum value is a broken SDK. Ids, timestamps and
   ciphertext are matchers (regex/type) — a different id from the real vault is not a broken SDK.

## Provider states and path generators

Every interaction that needs the vault in a specific condition declares a `providerStates` entry: a name plus
parameters. The vault's provider verification runs a state handler keyed by that exact name before replaying the
interaction, and is responsible for seeding whatever that state requires. `workspace_state()` (`_wire.py`) always
adds `workspace_id`, since almost every path is scoped to a workspace.

Request paths that embed those same values use `path(example, pattern=..., expression=...)` (`_wire.py`): `pattern`
is the regex matcher the consumer side checks the path against, and `expression` is a Pact `ProviderState`
generator — a template with `${name}` placeholders that the vault's state handler fills in with the *real* ids it
just seeded, so verification exercises the vault's own workspace and enrollment rather than guessing the
consumer's fixed ones (`ws-contract`, `enr-contract`, `pat-contract`). The placeholders currently in use:

- `${workspace_id}` — every path under `/api/external/v1/workspaces/{workspace_id}/...`.
- `${enrollment_id}` — the enrollment-poll path,
  `/api/external/v1/workspaces/{workspace_id}/session/registry/{enrollment_id}`.
- `${document_id}` — every path under `…/patients/{document_id}` and `…/exams/{document_id}`.
- `${version_id}` — the commit path, `…/versions/{version_id}/commit`, and the `expected_latest_version_id` a
  conflict-guarded reservation sends.
- `${node_id}` — `…/nodes/{node_id}`, and `node_ids[0]` in the confirmation of an upload.
- `${parent_id}` — the `parent_id` query parameter of the folder listing.

A value outside the path (a body field, a query parameter) is marked with `from_state(example, name)` (`_wire.py`).

The document and file states also carry `security_group_id` (`sg-contract`): it is the key of `encrypted_keys` in
every reservation, which no generator can rewrite, so the vault grants the service account that literal group.

Every provider state name in the current contract, and what the vault must seed for it:

| Provider state | Params | The vault must seed |
|---|---|---|
| `a service account can enroll an SDK session` | `workspace_id` | A workspace and a service-account token able to register hybrid public keys against `session/registry`. |
| `an admin approved the enrollment for one security group` | `workspace_id`, `enrollment_id` | A pending enrollment that an admin has approved, with at least one security group's DEK sealed to the SDK's registered public keys. |
| `an enrollment is waiting for an admin` | `workspace_id`, `enrollment_id` | An enrollment that exists but has not been approved or denied yet — `GET` on it returns `"status": "pending"`. |
| `an admin denied the enrollment` | `workspace_id`, `enrollment_id` | An enrollment an admin has explicitly denied — `GET` on it returns `"status": "denied"`. |
| `the vault no longer knows the enrollment` | `workspace_id`, `enrollment_id` | No enrollment at that id at all (expired and swept, or never existed) — `GET` on it returns `404`. |
| `an SDK session is active` | `workspace_id` | An active, signed session the vault will accept a `session/lock` request for. |
| `the SDK session holds the key of a security group` | `workspace_id`, `security_group_id` | An active session whose service account belongs to `security_group_id` and may create patients, exams and files in it, with storage budget. |
| `a patient has an uploaded version waiting to be committed` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | A patient in that group with `version_id` reserved on its `data` stream and the object already uploaded, so the commit finds it. |
| `an exam has an uploaded version waiting to be committed` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | The same for an exam (no stream segment in its routes); `meta.patient_id` set. |
| `a patient has one committed version` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | A patient in that group with one committed `data` version (`version_id`), an `encrypted_index`, no pending version and no draft; the only live patient the service account can list (the list interaction reads one page whose every row has that shape). |
| `a patient has a draft newer than its latest version` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | As above, plus a `data` draft head whose `updated_at` is later than the latest version's `created_at`. |
| `a patient has a committed version and another one pending` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | One committed `data` version plus an unexpired pending reservation made by **another** account (the vault lets an account replace its own), so a new reservation answers `409 DocumentVersionPending`. |
| `an exam has one committed version` | `workspace_id`, `security_group_id`, `document_id`, `version_id` | An exam in that group with one committed version, an `encrypted_index` and `meta.patient_id`. |
| `a file was uploaded and awaits confirmation` | `workspace_id`, `security_group_id`, `node_id` | A single-mode file node, staged by the service account in that group with a `mime_type`, still `pending`, whose object is already in R2 — so `uploads/complete` reports it `ready`. |
| `a folder holds one ready file` | `workspace_id`, `security_group_id`, `parent_id`, `node_id` | A folder (`parent_id`) in that group holding exactly one node: a ready single-mode file with a `mime_type` and a `size`. |

## How to add an interaction, step by step

1. **Pick or add a test file** in `contracts/tests/` for the area of behaviour (`test_clock.py`, `test_session.py`,
   or a new `test_<area>.py` for a new surface).
2. **Declare the interaction** on the `pact` fixture: `pact.upon_receiving("a description in plain English")`, then
   `.given(state_name, params)` if it needs a provider state (use `workspace_state()` from `_wire.py` to always
   carry `workspace_id`), `.with_request(...)`, `.with_headers(...)` (reuse `bearer_header()` /
   `signed_headers()` from `_wire.py`), `.with_body(...)`, `.will_respond_with(status)`, `.with_body(...)` for the
   response.
3. **Apply the matcher/literal rules above** to every field of the response body: `match.regex`/`match.str`/
   `match.int`/`match.each_like` for shape-only fields, a bare value or `literal(...)` (`_wire.py`) for anything the
   SDK branches on.
4. **Exercise real SDK code** against `pact.serve()`'s mock server — build a transport with `make_transport()`
   (`conftest.py`) or call the higher-level function/method under test (`enroll()`, `SessionManager.lock()`, a new
   resource method) — never hand-written HTTP via `httpx` directly against the mock server.
5. **Assert on the SDK's return value**, not on the raw HTTP — the point is that the SDK correctly parsed what the
   contract says the vault sends.
6. **Run `make contract`.** If the test passes and the whole suite passes, `contracts/diagnos-sdk-diagnos-vault.json`
   is regenerated with your interaction included, normalized and sorted in with the rest.
7. **Commit the regenerated file together with the test.** CI's `make contract-check` fails a PR that changes SDK
   HTTP behaviour without a matching contract change (see [`../CONTRIBUTING.md`](../CONTRIBUTING.md)).

## Reading a contract diff in a pull request

The file is sorted and normalized, so a diff is meaningful, not noise from reordering. When reviewing one, check:

- **A new interaction** (new `description`/`providerStates` block): does the PR's test justify it, and does the
  provider-state name read like something the vault's state handler can plausibly seed? If it is a genuinely new
  state name, the vault side needs a matching handler before verification can pass there — call that out in the PR.
- **A changed `matchingRules` regex or a changed literal value**: this is the signal that the SDK now requires a
  different shape or branches on a different literal than before — it should trace to a corresponding SDK code
  change in the same PR, not appear on its own.
- **A response body field disappearing**: the SDK stopped reading it. Confirm that's intentional (dead code removed)
  and not a field the SDK still needs but the test no longer asserts.
- **A `pactRust`/tool-version-shaped diff**: should not happen — normalization strips `metadata.pactRust`
  specifically to prevent this. If you see one, something bypassed `normalize()`/`render()`.

## Current scope, and what is not here

The contract covers: the vault's clock (`GET /time`); enrollment (registration, and polling through
pending/approved/denied/forgotten); lock (`POST session/lock`); versioned documents — creating a patient or an exam
(reserve, commit), opening the latest version, preferring a newer draft, reserving the next version under the
conflict guard, archiving without a new version, listing, and backing off on a pending version; and files — reserving
a file, confirming it, reading a ready file (its sealed name, its body and the SSE-C key storage demands), listing a
group's files, and creating a folder.

**Multipart uploads are not here.** The vault opens, completes and aborts them through R2's S3 endpoint, and its
provider verification runs a local `wrangler dev` with no such endpoint, so those interactions could not be
verified there. The SDK's unit tests cover them against a double of the vault's routes
(`apps/sdk/tests/resources/vault_double.py`); they join the contract once the provider has an S3 double. See
[`../docs/COMPATIBILITY.md`](../docs/COMPATIBILITY.md).
