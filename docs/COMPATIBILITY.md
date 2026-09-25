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
| Patients, exams | `vault.patients`, `vault.exams` (versioned documents) | ✅ Compatible | contract + web-app vectors |
| Files | `vault.drives` | ⚠️ Earlier protocol revision | — |

The CLI (`diagnos-cli`) and the API (`diagnos-api`) are thin shells over the SDK: every command and route inherits
its row. Commands and routes for files inherit the ⚠️.

"Verified by contract" means the SDK's side is pinned in
[`contracts/diagnos-sdk-diagnos-vault.json`](../contracts/diagnos-sdk-diagnos-vault.json) and the vault replays it in
its own repository (provider verification). "Web-app vectors" means the SDK opens bytes sealed by the web app's own
code ([`document_content.json`](../apps/sdk/tests/vectors/document_content.json)) and the contract's oracles seal
them with an independent implementation — a document the SDK writes is one the web app opens, and the other way
round.

## Patients and exams

The SDK follows the web app step for step:

- A document belongs to exactly one security group (`security_group_id`). Its data key (DEK) is sealed for that
  group with the same label the web app uses for every document.
- Writing is reserve → signed `PUT` → commit. Each version is sealed under its own key, derived from the DEK and the
  `security_context` the vault returns next to the signed URL; the body is raw `salt ‖ nonce ‖ ciphertext`.
  Patients have two streams, so their version routes carry `/streams/data`; exams do not.
- Every write carries the sealed summary (`encrypted_index`: names and tags, or title, modality and date), so lists
  open without downloading any version — `vault.patients.list()` returns them already decrypted.
- Reading follows the web app's rule: the editor's draft wins when it is newer than the latest version
  (`include_draft=False` reads committed versions only).
- Archive and delete are flag changes without a new version (`restore` undoes a delete).
- `expected_latest_version_id` makes the vault refuse a write if someone saved in between; a reservation that finds
  another writer's pending version is retried briefly, then raised.

### Known limits

- **The patient's `file` stream** (the web editor's rich document, Lexical + Yjs) is not exposed; the SDK reads and
  writes the structured `data` stream.
- **Identity documents** (`identifiers[].value`, e.g. CPF) are sealed by the vault's sensitive-data route, which the
  external API does not offer. The SDK carries existing values through a read-modify-write untouched and refuses a
  plain-text value.
- **Anonymization precision**: the web app truncates every date to the workspace's `time_precision` before
  encrypting. The external API does not expose that setting; set `DIAGNOS_TIME_PRECISION` to the workspace's value
  and the SDK applies the same truncation.
- **Drafts** are read, never written: the SDK's writes are committed versions.
- **Report templates** have no external route; they are only in the web app.
- **SSE-C**: document objects are stored without SSE-C, exactly as the web app stores them (a second layer only one
  side sent would make the object unreadable to the other). The body is end-to-end encrypted either way.

## Files

The file layer of the SDK was written against an earlier revision of the vault protocol:

- Drive routes moved from `…/drives/{security_group_id}/…` to `…/nodes/…`, with `security_group_id` in the body or
  the query string.
- Every file gets its own data key, wrapped for each security group in `encrypted_keys`; the file name is encrypted
  under that key, and content keys are derived through the same `security_context` scheme as documents.

Do not use `vault.drives` against the production vault yet. Its calls fail loudly — a validation error, a `400` or a
`404` — before anything is stored, so no data the web app could not read gets written.

## The way back to green

1. ~~Documents~~ — done: current routes and models, web-app vectors, contract interactions.
2. Files: `/nodes` routes, per-file keys, encrypted names, `security_context` content keys.
3. Entropy: contribute the SDK's own `random_seed` in request bodies (the vault already accepts it; today the SDK
   only consumes the vault's).

Follow progress in the [issue tracker](https://github.com/diagnos-tech/integration/issues).
