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
| Files and folders | `vault.drives` (`/nodes`: reserve, `PUT`, confirm, multipart, list, read, folders) | ✅ Compatible | contract + web-app vectors |

The CLI (`diagnos-cli`) and the API (`diagnos-api`) are thin shells over the SDK: every command and route inherits
its row.

"Verified by contract" means the SDK's side is pinned in
[`contracts/diagnos-sdk-diagnos-vault.json`](../contracts/diagnos-sdk-diagnos-vault.json) and the vault replays it in
its own repository (provider verification). "Web-app vectors" means the SDK opens bytes sealed by the web app's own
code ([`document_content.json`](../apps/sdk/tests/vectors/document_content.json),
[`node_content.json`](../apps/sdk/tests/vectors/node_content.json)) and the contract's oracles seal them with an
independent implementation — what the SDK writes is what the web app opens, and the other way round.

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

## Files and folders

`vault.drives` follows the web app's upload pipeline (`@repo/magic-files`) step for step:

- Every file and every folder is a node with its own data key, wrapped for its security group; its name is sealed
  under that key.
- The body is libsodium secretstream in 1 MiB frames, under a key derived from the node's key and the
  `security_context` the vault returns at reservation. Its size is computed before encryption, and the vault signs
  the upload for exactly that size.
- Up to 100 files per reservation. Files up to 64 MiB go up in one signed `PUT` each and are confirmed together;
  larger ones go up in 32 MiB parts, signed in waves of up to 200 as the upload advances, and are aborted on failure
  so the vault releases the reserved bytes at once.
- R2's SSE-C layer uses the web app's key (the content key's sister) on the `PUT`, on every part and on the `GET`.
- Folders: `create_folder`, and `parent_id` on upload and list.
- Reading needs only the node id: the name, the content and the SSE-C key all open with the group key.

The contract pins reserve → `PUT` → confirm, read + download, list and folder creation. Multipart uploads are
covered by unit tests against a double of the vault's routes instead: the vault opens and closes them through R2's
S3 endpoint, which its provider verification (a local `wrangler dev`) does not have.

### Known limits

- **Optimized variants** (thumbnails, web-friendly transcodes) are produced by the vault only when a node's key is
  also escrowed for its media processor (`system:smartlake:v1` in `encrypted_keys`). The web app does not send that
  escrow today and neither does the SDK, so neither gets variants; `optimized_variants` is reported as the vault
  returns it.
- **Delete, move and rename** have no external route yet.
- **Upload progress**: `upload_many` blocks per batch of 100; there is no per-byte progress callback yet.
- **Names are paths**: the web app seals a relative path as a file's name. The CLI and the API only ever use its last
  segment as a local file name.

### Open on the vault side

None of these changes a byte the SDK sends. They are questions for the vault, recorded so nobody has to rediscover
them:

- **Unsigned SSE-C headers.** The vault signs only `content-length` (and `content-type`) and leaves the SSE-C
  headers out of the signature on purpose, since signing them would require knowing the key. Its own `TODO` asks
  whether R2 accepts unsigned `x-amz-server-side-encryption-*` headers on a presigned URL; if not, the plan is to
  drop SSE-C. Meanwhile the web app's upload code asserts those headers *are* signed and stops before sending. One of
  the two will change; the SDK sends what the vault documents today and will follow the outcome.
- **SSE-C on multipart.** Parts are sent with SSE-C, as the web app does, but the vault opens multipart uploads
  without SSE-C parameters. S3 semantics expect both to agree; this needs confirming against R2 for files above
  64 MiB.
- **The web viewer** does not read nodes yet (`fileViewer.ts`). Interoperability is proven at the byte level —
  vectors generated by the web app's upload code — rather than through the viewer.

## What is next

1. ~~Documents~~ — done: current routes and models, web-app vectors, contract interactions.
2. ~~Files~~ — done: `/nodes` routes, per-file keys, sealed names, `security_context` content keys, SSE-C, folders.
3. Multipart in the contract, once the provider verification has an S3 double for R2.
4. Entropy: contribute the SDK's own `random_seed` in request bodies (the vault already accepts it; today the SDK
   only consumes the vault's).

Follow progress in the [issue tracker](https://github.com/diagnos-tech/integration/issues).
