# Compatibility with the vault

**English** · [Português (Brasil)](COMPATIBILITY.pt-BR.md)

What in this repository works against today's vault (`https://vault.diagnos.health`), what does not yet, and why.
It is kept honest by the [contract tests](../contracts/README.md): an interaction is only in the contract once the
SDK speaks the vault's current protocol for it.

## At a glance

| Area | SDK surface | Status | Verified by |
|---|---|---|---|
| Clock | `GET /time`, skew correction | ✅ Compatible | contract |
| Identity | `DIAGNOS_API_TOKEN` (`apikey-<jwt>`), `Authorization: Bearer` | ✅ Compatible | contract |
| Request signature | `X-Signature-Timestamp` / `-Nonce` / `-Hmac` | ✅ Compatible | contract + vectors |
| Enrollment | `session/registry` (register, poll: pending, approved, denied, expired) | ✅ Compatible | contract |
| Session keys | hybrid seal (X25519 + ML-KEM-768), `random_seed` | ✅ Compatible | contract + vectors |
| Lock | `session/lock` | ✅ Compatible | contract |
| OpenBao auto-unseal | save/restore of the unlocked session | ✅ Client-side only | unit tests |
| Patients, exams | `vault.patients`, `vault.exams` (versioned documents) | ⚠️ Earlier protocol revision | — |
| Files | `vault.drives` | ⚠️ Earlier protocol revision | — |

The CLI (`diagnos-cli`) and the API (`diagnos-api`) are thin shells over the SDK: `login`, `status` and session
commands work today; commands and routes for patients, exams and files inherit the ⚠️ rows.

The cryptographic primitives themselves are not the problem: the SDK's suite passes against vectors freshly
regenerated from the vault's reference implementation (request signature, key envelope, content envelope, hybrid
seal, secretstream framing). What changed is how the vault *composes* them for documents and files.

## What changed in the vault

The document and file layers of the SDK were written against an earlier revision of the vault protocol. Since then the
vault changed in ways that are not renames:

**Versioned documents (patients, exams)**

- A document belongs to exactly one security group: `security_group_id` (a string) replaced `security_groups` (a list),
  in requests and in the index.
- Version state moved under `document.streams.<stream>` (`latest_version_id`, `versions`, `pending_version_id`).
  Patients have two streams (`data`, `file`), so their version routes gained a segment:
  `…/{document_id}/streams/{stream}/versions[/{version_id}/commit]`.
- Creating a patient requires an `encrypted_index`: a small summary encrypted under the document key, so lists and
  search never open the full record.
- The content of each version is encrypted under a per-version key derived from a `security_context` that the vault
  returns next to every signed upload/download URL, and the object body is raw bytes (`salt ‖ nonce ‖ ciphertext`),
  not a JSON envelope.

**Files**

- Drive routes moved from `…/drives/{security_group_id}/…` to `…/nodes/…`, with `security_group_id` in the body or
  the query string.
- Every file gets its own data key, wrapped for each security group in `encrypted_keys`; the file name is encrypted
  under that key, and content keys are derived through the same `security_context` scheme as documents.

## What this means for you

- Enrolling, holding a session and making signed requests work today.
- Do not use `vault.patients`, `vault.exams` or `vault.drives` against the production vault yet. Today those calls
  fail loudly — a validation error, a `400` or a `404` — before anything is stored, so no data the web app could not
  read gets written. They remain in the package as a preview so the API shape can be reviewed.

## The way back to green

Each item lands as its own pull request, together with its contract interactions, so the vault's provider
verification proves it before it ships:

1. Documents: models (`security_group_id`, `streams`), stream-aware routes, `encrypted_index` for patients,
   `security_context` content keys and raw-byte bodies — with vectors regenerated from the vault's reference
   implementation.
2. Files: `/nodes` routes, per-file keys, encrypted names, `security_context` content keys.
3. Entropy: contribute the SDK's own `random_seed` in request bodies (the vault already accepts it; today the SDK
   only consumes the vault's).

Follow progress in the [issue tracker](https://github.com/diagnos-tech/integration/issues).
