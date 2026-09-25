# PROTOCOL — the contract between the SDK and the vault

**English** · [Português (Brasil)](PROTOCOL.pt-BR.md)

Normative. Every format below is pinned by `apps/sdk/tests/vectors/*.json`,
generated from the vault's reference implementation. When this document and
a vector disagree, the vector wins and this document has a bug.

> [!NOTE]
> Sections [8](#8-versioned-documents) and [9](#9-drives-files) describe the
> `diagnos` SDK's 0.1 implementation of patients, exams and drive files,
> which predates the vault's current protocol revision. See
> [COMPATIBILITY.md](COMPATIBILITY.md) for exactly what is and is not
> compatible with `vault.diagnos.health` today. Everything else in this
> document — conventions, identity, clock, signature, session keys and the
> response seed, enrollment, the hybrid seal, frozen labels, SSE-C, OpenBao
> auto-unseal, errors and limits — is accurate to the vault as it runs
> today.

## 0. Conventions

- `b64url` = RFC 4648 §5 **without padding**. `hex` = lowercase. JSON is
  UTF-8. Ids are opaque strings. Time: `expires_at`/`*_at` **numbers** are
  Unix seconds (`_ms` = milliseconds); `created_at`/`updated_at`/`completed_at`
  on indexes and nodes are ISO-8601 **strings**.
- Base URL: `https://vault.diagnos.health`. SDK audience: `/api/external/v1`.
- Every response is an envelope:
  ```json
  { "success": true,  "status": "success", "status_code": 200, "result": {…}, "docs": "https://vault.diagnos.health/docs" }
  { "success": false, "status": "fail",    "status_code": 4xx, "errors": [{ "code": "QuotaExceeded", "message": "…", "trace_id": null }], "docs": "…" }
  ```
  Decide by `code`, never by `message`. `X-Request-Id` is on every response.
  `GET /time` (§2) is the one exception: it answers a raw `{"result": …}`,
  with no envelope.

## 1. Identity

`DIAGNOS_API_TOKEN` is `apikey-<JWT EdDSA>`, issued by a workspace admin.
Claims the SDK reads: `sub` (key id, rotatable), `account_id`,
`workspace_id`, `name` (`slug@<workspace_id>.diagnos.health`). The token also
carries `iss`, the vault's issuer — not checked by the SDK, since the SDK
never verifies the JWT signature at all: it has no key to verify it with,
and the vault is the only party that does. `workspace_id` is read from the
payload only to build URLs; there is no `exp` claim, and revocation is
server-side, surfacing as `403 ServiceAccountRevoked` on the next signed
call.

Header on every request: `Authorization: Bearer apikey-<jwt>`.

## 2. Clock

Signatures carry a timestamp the vault checks within ±120 s of its own
clock. Before the first signed request: `GET /time`, no auth, no envelope →
`{"result": <server_ms>}`. Offset = `server_ms − local_ms`; take the median
of three round trips. On `401 SignatureTimestampSkew`, resync and retry
once.

## 3. Request signature

Every request except `GET /time` and `session/registry` (both the `POST`
and the `GET` poll) carries three headers:

```
X-Signature-Timestamp: <unix seconds, decimal, server clock>
X-Signature-Nonce:     <≥16 random bytes, b64url; unique per request>
X-Signature-Hmac:      <hex(HMAC-SHA512(sign_key, canonical))>
```

`canonical` is six fields joined by `\n` (0x0A), encoded as UTF-8:

```
METHOD \n PATH \n QUERY \n TIMESTAMP \n NONCE \n sha256hex(BODY)
```

1. `METHOD` uppercase ASCII.
2. `PATH` exactly as sent on the wire, percent-encoded, **never decoded**
   (`/api/external/v1/workspaces/ws%201/patients`).
3. `QUERY` without `?`; split on `&`, sort the raw `k=v` pairs by code
   point, join with `&`; empty string when there is no query.
4. `TIMESTAMP` the exact header text.
5. `NONCE` the exact header text.
6. SHA-256 hex of the raw body bytes; an empty body hashes the empty string
   (`e3b0c442…b855`).

A `(timestamp, nonce)` pair is single-use: the vault answers
`409 ReplayDetected` to a byte-identical resend. Retries generate a new pair.

Vector: `request_signature.json`.

## 4. Session keys and the response seed

A session is `session_id`, `sign_key` (32 B, HMAC) and `enc_key` (32 B,
AES-256-GCM), valid until `expires_at`.

Every response to a signed request carries `random_seed` in its JSON
envelope:

```json
{ "random_seed": { "nonce": "<b64url>", "ciphertext": "<b64url>" }, "result": {…}, … }
```

`random_seed` = AES-256-GCM(`enc_key`, iv = `nonce` (12 B), AAD =
UTF-8(`session_id`)) over the JSON `{"seed": "<32 B b64url>"}`. It travels
in the body, not a header, so it stays out of proxy and APM logs, which
record headers far more often than bodies.

The SDK mixes the seed into its own entropy instead of trusting it alone:

```
state = SHA-256(seed)
block = SHA-256(os_random(32) ‖ state ‖ counter)   # counter resets to 0 on every new seed
```

`os_random(32)` always dominates each block, so a seed of all zeros degrades
gracefully to plain OS randomness, never to something weaker — the seed
augments `os.urandom`, it never replaces it. The reference SDK opens, parses
and decodes `random_seed` inside its memory enclave (`apps/sdk/native/README.md`);
it never exists as a Python object.

The vault also accepts an optional client-contributed `random_seed` field in
a signed request's own body, for the SDK to contribute entropy back. This
SDK does not send one yet — it only consumes the vault's.

Vector: `aes_gcm_envelope.json` covers the AEAD; `hybrid_seal.json` covers
the sealing that delivers `sign_key`/`enc_key` in the first place (§6).

## 5. Enrollment

```
POST /api/external/v1/workspaces/{workspace_id}/session/registry      (Bearer only, unsigned)
{ "public_keys": { "x25519": "<32 B b64url>", "mlkem768": "<1184 B b64url>" },
  "runtime": { "sdk_name": "diagnos-python", "sdk_version": "0.1.0", "language": "python 3.12",
               "os": "linux", "arch": "x86_64", "hostname"?: "…", "user"?: "…",
               "container": true, "cloud"?: "aws" } }
→ 201 { "enrollment_id", "code": "123456", "approval_url", "expires_at", "poll_interval_seconds" }
```

Print `approval_url` and `code` to the terminal. A workspace admin opens
the link, reads the runtime description, types the code and picks security
groups. Poll every `poll_interval_seconds` until `expires_at`:

```
GET /api/external/v1/workspaces/{workspace_id}/session/registry/{enrollment_id}   (Bearer only)
→ { "status": "pending" } | { "status": "denied" }
  | { "status": "approved", "approval": { "session_id", "session_expires_at",
        "sealed_session": <HybridSeal>, "sealed_group_keys": { "<security_group_id>": <HybridSeal>, … } } }
```

- `sealed_session` opens (AAD = `enrollment_id`) to the JSON
  `{"session_id","sign_key":"<32 B b64url>","enc_key":"<32 B b64url>","expires_at"}`.
- Each `sealed_group_keys[sg]` opens (AAD = `enrollment_id`) to the **raw
  32-byte DEK** of that security group — not JSON, not base64.
- `POST /api/external/v1/session/lock` (signed, no body) ends the session.

A `404` on the poll after `expires_at` (`SdkEnrollmentNotFound`) means the
same thing as the client's own deadline check: the approval window is
closed either way.

## 6. HybridSeal — X25519 + ML-KEM-768

The same construction seals the session (vault → SDK) and the group DEKs
(web app → SDK).

```
eph            = X25519.keygen()
ss1            = X25519(eph.secret, recipient.x25519)                 32 B
(kem_ct, ss2)  = ML-KEM-768.encaps(recipient.mlkem768)                1088 B, 32 B
encapsulation  = eph.public ‖ kem_ct                                  1120 B
key            = HKDF-SHA256(ikm = ss1 ‖ ss2, salt = ∅, info = utf8("imgexam-sdk-hybrid-seal-v1") ‖ encapsulation, L = 32)
nonce          = random(12)
ct             = AES-256-GCM(key, nonce, plaintext, aad = utf8(aad))  (tag appended, 16 B)
wire           = { "salt": b64url(encapsulation), "nonce": b64url(nonce), "ciphertext": b64url(ct) }
```

`imgexam-sdk-hybrid-seal-v1` is a frozen label — see [Frozen labels](#frozen-labels).

Opening: split `salt` into `eph.public[0:32]` and `kem_ct[32:]`, derive
`ss1 = X25519(sk.x25519, eph.public)` and `ss2 = ML-KEM-768.decaps(sk.mlkem768, kem_ct)`,
same HKDF, AES-GCM decrypt. Both secrets must be present: the design survives
either primitive being broken alone — a future quantum break of X25519 still
needs ML-KEM-768 broken too, and a flaw in ML-KEM's newer implementation
still leaves X25519 standing.

Vector: `hybrid_seal.json` (contains the recipient secret keys).

## 7. Key and content envelope

`EncryptedPayload` (`{salt, nonce, ciphertext}`, all b64url) is the one
symmetric envelope of the product.

```
salt     = random(16)
derived  = HKDF-SHA256(ikm = wrapping_key, salt = salt, info = utf8(info), L = 32)
nonce    = random(12)
ct       = AES-256-GCM(derived, nonce, plaintext, aad = ∅)          (tag appended)
```

`wrapKey` (plaintext is a key) and `encryptContent` (plaintext is data)
are the same bytes; only `info` changes. `info` strings are versioned and
never shared between purposes — the full, frozen list is in
[Frozen labels](#frozen-labels) below.

Vector: `aes_gcm_envelope.json` (HKDF, wrapKey, encryptContent).

## Frozen labels

Every HKDF/AAD label below keeps its historical `imgexam-` prefix on
purpose. The name predates `diagnos`, but these strings are wire constants
baked into every ciphertext already stored — renaming one would make
existing data unreadable. Never repurpose a label for a new meaning; a
changed derivation gets a new, separately versioned string (`-v2`) instead.
Code that uses one of these points back here by name — see
`apps/sdk/src/diagnos/crypto/keys.py`, `hybrid.py` and `hkdf.py`.

| Label | Purpose | Section |
|---|---|---|
| `imgexam-sdk-hybrid-seal-v1` | HKDF `info` for the hybrid seal (session and group-key sealing) | §6 |
| `imgexam-patient-dek-v1` | wraps a patient document's DEK under its security group's DEK | §7, §8 |
| `imgexam-exam-dek-v1` | wraps an exam document's DEK | §7, §8 |
| `imgexam-template-dek-v1` | wraps a template document's DEK | §7, §8 |
| `imgexam-patient-record-v1` | encrypts a patient record's body | §7, §8 |
| `imgexam-exam-record-v1` | encrypts an exam record's body | §7, §8 |
| `imgexam-template-record-v1` | encrypts a template record's body | §7, §8 |
| `imgexam-drive-node-key-v1` | derives a drive node's content key from its group DEK (salted by `node_id`) | §9 |
| `imgexam-drive-node-name-v1` | wraps a drive node's file name under the group DEK | §9 |
| `imgexam-sse-c-v1` | derives the optional SSE-C customer key from a document or node key | §10 |

## 8. Versioned documents

> [!WARNING]
> This section describes the SDK 0.1 implementation of patients, exams and
> templates, which predates the vault's current protocol revision — see
> [COMPATIBILITY.md](COMPATIBILITY.md). It is kept here as a record of what
> `vault.patients`/`vault.exams` (labelled **preview** in
> [`apps/sdk/README.md`](../apps/sdk/README.md)) send and expect today, not as a
> description of what `vault.diagnos.health` currently accepts.

Patients, exams and templates share one model: a Firestore **index** the
API exposes (versions, latest, groups, wrapped keys, clear `meta`) and, per
version, an encrypted object in R2 the SDK reads/writes through signed URLs.
Only the SDK ever sees plaintext.

Index (`result.document`):
```json
{ "document_id", "workspace_id", "resource": "patients", "security_groups": ["sg1"],
  "encrypted_keys": { "sg1": <EncryptedKeyPayload> }, "latest_version_id", "versions": [{ "version_id", "size", "created_at", "created_by" }],
  "pending_version_id", "meta": {…}, "created_at", "created_by", "updated_at", "updated_by", "is_archived", "is_deleted" }
```

Keys:
- `doc_dek` = 32 random bytes, one per **document** (versions reuse it).
  `encrypted_keys[sg]` = `wrapKey(group_dek[sg], doc_dek, "imgexam-<singular>-dek-v1")`
  (see [Frozen labels](#frozen-labels) for the three concrete strings).
- Object body = UTF-8 JSON of `encryptContent(doc_dek, utf8(json(record)), "imgexam-<singular>-record-v1")`,
  i.e. `{"salt":…,"nonce":…,"ciphertext":…}`. `Content-Type: application/json`.

Records (JSON before encryption):
- `patients` — mirrors `@repo/core/schemas/Patient.ts#PatientRecord`:
  `legal_name`, `display_name`, `legal_id?`, `external_id?`, `birth_date?` (ISO date),
  `biological_sex?` (`MALE|FEMALE|INTERSEX|UNDEFINED`), `gender_identity?`, `race_identity?`,
  `internal_notes?: string[]`, `email?`, `phone?`, `custom_attributes?: object`.
- `exams` — `title?`, `description?`, `report?: { format: "html"|"markdown"|"text", content }`, `custom_attributes?: object`.
- `templates` — `title`, `content_html`, `category?`. (web client only.)

`meta` (clear): patients `{ specialist_ids? }` · exams `{ patient_id, modality?, report_status?, dicom_manifest_status?, … }` · templates `{ category? }`.

Routes (`{base}` = `/api/external/v1/workspaces/{workspace_id}/{resource}`):
```
GET  {base}?limit=&cursor=&security_group_id=&include_deleted=      → { items: [index…], next_cursor }
POST {base}   { security_groups, encrypted_keys, content_length, meta? }
              → 201 { document, version_id, upload: { url, method: "PUT", headers: { "content-length" }, expires_at } }
PUT  upload.url   (body = encrypted object; header content-length EXACTLY as given)
POST {base}/{document_id}/versions/{version_id}/commit               → { document }
GET  {base}/{document_id}?version_id=                                 → { document, version, download: { url, method: "GET", expires_at } }
POST {base}/{document_id}/versions   { content_length, meta?, is_archived?, is_deleted? }
              → 201 { document, version_id, upload }   then PUT, then commit
```

There is no partial update and no delete: a change is a new full
version; archival/deletion are flags on the index set through a new version.
Only the principal that staged a version may commit it.

## 9. Drives (files)

> [!WARNING]
> This section describes the SDK 0.1 implementation of drive files, which
> predates the vault's current protocol revision — see
> [COMPATIBILITY.md](COMPATIBILITY.md). It is kept here as a record of what
> `vault.drives` (labelled **preview** in
> [`apps/sdk/README.md`](../apps/sdk/README.md)) sends and expects today, not as a
> description of what `vault.diagnos.health` currently accepts.

A drive is a security group. Any file (DICOM, image, video, PDF) is a
**node** in `{base}` = `/api/external/v1/workspaces/{workspace_id}/drives/{security_group_id}`.

Keys:
```
node_key       = HKDF-SHA256(ikm = group_dek, salt = utf8(node_id), info = utf8("imgexam-drive-node-key-v1"), L = 32)
encrypted_name = wrapKey(group_dek, utf8(original_file_name), "imgexam-drive-node-name-v1")
```
Deriving the content key from the group DEK means a node needs no wrapped
key of its own and revocation happens at the group. The name is wrapped with
the **group DEK** (not the node key) because it travels in the staging
request, before the vault has assigned a `node_id` — the node key's own
derivation needs that id as salt, which does not exist yet at that point.

Body (`secretstream.json`): libsodium `crypto_secretstream_xchacha20poly1305` with `node_key`,
framed as `[header 24 B][len uint32 BE][cipher chunk]*`; plaintext chunks of
1 MiB (`1048576`), last chunk pushed with `TAG_FINAL` (an empty file still has one final chunk).
The reader re-assembles frames by length before pulling; parts of a multipart
upload split the framed byte stream at arbitrary offsets.

Routes:
```
POST {base}/uploads   { exam_id?, files: [{ client_ref, size (encrypted bytes), mime_type?, encrypted_name? }] (≤1000) }
   → 201 { nodes: [ { client_ref, node_id, mode: "single", upload } | { client_ref, node_id, mode: "multipart", part_size, part_count } ] }
PUT  upload.url                                   (single: ≤ 64 MiB, content-length exact)
POST {base}/uploads/complete   { node_ids }       → { ready: [node…], missing: [node_id…] }
POST {base}/uploads/{node_id}/multipart           → { upload_id, part_size (32 MiB), part_count }
POST {base}/uploads/{node_id}/multipart/parts   { part_numbers (≤200) } → { parts: [{ part_number, url, expires_at }] }
PUT  part.url  (ETag from response header)  …  POST {base}/uploads/{node_id}/multipart/complete { parts: [{ part_number, etag }] } → { node }
POST {base}/uploads/{node_id}/multipart/abort     → { aborted: true }
GET  {base}/nodes?limit=&cursor=&exam_id=&include_pending=          → { items: [node…], next_cursor }
GET  {base}/nodes/{node_id}                        → { node, download }
```

`size` is the size of the **encrypted, framed** body — compute it before
uploading (`24 + Σ(4 + chunk + 17)`, from the header, the length prefix and
the 17-byte secretstream tag per chunk). The vault charges the workspace by
it.

## 10. SSE-C (opt-in)

Objects are already end-to-end encrypted. Additionally, single PUT/GET
may use R2's SSE-C with a key the vault never sees. Disabled by default until
the web client adopts it (`DIAGNOS_SSE_C=1` enables); never used for multipart
(the vault creates that upload and must not hold the key).

```
sse_key = HKDF-SHA256(ikm = doc_dek | node_key, salt = ∅, info = utf8("imgexam-sse-c-v1"), L = 32)
x-amz-server-side-encryption-customer-algorithm: AES256
x-amz-server-side-encryption-customer-key:       base64(sse_key)         (standard base64, with padding)
x-amz-server-side-encryption-customer-key-MD5:   base64(MD5(sse_key))
```

## 11. OpenBao auto-unseal

Optional. When `OPENBAO_ADDR` and `OPENBAO_TOKEN` are set, the SDK saves
its unlocked state after a successful enrollment and restores it on start,
so a restart needs no human. This deliberately moves the group DEKs from RAM
to OpenBao's encrypted storage: whoever can read that path can read the
workspace. Scope the token to the path.

KV v2 · `mount = OPENBAO_MOUNT (default "secret")`, path `OPENBAO_PATH_PREFIX (default "diagnos")/{workspace_id}/{account_id}`:
```json
{ "v": 1, "enrollment_id", "x25519_secret", "mlkem768_secret", "session_id", "sign_key", "enc_key",
  "session_expires_at", "group_keys": { "<sg>": "<32 B b64url>" }, "saved_at" }
```
Restore only while `session_expires_at − now > 60 s`; otherwise enroll again.

`OPENBAO_TOKEN_FILE` may name a file holding the token instead of `OPENBAO_TOKEN`
(the form container orchestrators prefer). Writing this document is the one
moment the reference SDK's keys leave locked memory: they are revealed into
buffers that are zeroed right after the request is built.

## 12. Errors

| `code` | HTTP | SDK exception |
|---|---|---|
| `ValidationError` | 400 | `ValidationError` |
| `Unauthorized`, `SessionNotFound`, `SignatureInvalid`, `SignatureMissing` | 401 | `AuthenticationError` (session gone → re-enroll) |
| `SignatureTimestampSkew` | 401 | resync clock, retry once, then `AuthenticationError` |
| `QuotaExceeded`, `BudgetNotProvisioned` | 402 | `QuotaError` |
| `ServiceAccountRevoked`, `DocumentAccessDenied`, `InsufficientPermission`, `NotAWorkspaceMember` | 403 | `DiagnosPermissionError` |
| `DocumentNotFound`, `DocumentVersionNotFound`, `DriveNodeNotFound`, `SdkEnrollmentNotFound`, `NotFound` | 404 | `NotFoundError` |
| `DocumentVersionPending`, `DocumentVersionNotPending`, `ReplayDetected`, `DriveNodeNotPending` | 409 | `ConflictError` (`ReplayDetected` is retried once with a new nonce) |
| `RateLimitExceeded` | 429 | `RateLimitError` (honour `Retry-After` if present; else a jittered backoff, up to 3 retries) |
| `RequestBodyTooLarge` | 413 | `ValidationError` |
| 5xx / `InternalServerError` | 5xx | `VaultError` (carries `trace_id`; one retry after a fixed backoff) |

A response that is not valid JSON at all (a proxy's error page, a truncated
body) never carries a `code`; the SDK raises `VaultError` with the synthetic
code `InvalidResponse` instead of leaking a bare parse error. `SessionExpiredError`
is a purely local error — the SDK has no live session to sign with — and
never comes from a vault response.

## 13. Limits

API body 1 MiB · document version ≤ 64 MiB · batch ≤ 1000 files · single file ≤ 64 MiB · multipart part 32 MiB, ≤ 200 part URLs per call · list page ≤ 200.
