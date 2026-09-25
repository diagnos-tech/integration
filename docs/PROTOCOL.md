# PROTOCOL — the contract between the SDK and the vault

**English** · [Português (Brasil)](PROTOCOL.pt-BR.md)

Normative. Every format below is pinned by `apps/sdk/tests/vectors/*.json`,
generated from the vault's reference implementation. When this document and
a vector disagree, the vector wins and this document has a bug.

The whole document matches `vault.diagnos.health` and the web app as they run
today. Questions still open on the vault side — none of which change a byte
the SDK sends — are tracked in [COMPATIBILITY.md](COMPATIBILITY.md).

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

`EncryptedPayload` (`{salt, nonce, ciphertext}`, all b64url) is the
symmetric envelope for keys and small JSON payloads.

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

Stored objects (a document version, a draft head) never use a long-lived
key directly. Each object gets its own **content key**, derived from the
document's DEK and the `security_context` the vault returns next to every
signed upload/download URL — opaque to the client, bound by the vault to
the object's real address:

```
content_key = HKDF-SHA256(ikm = dek, salt = utf8(key_id), info = utf8(security_context.value), L = 32)
key_id      = version_id                           (a committed version)
            = "draft"  |  "draft:<stream>"         (a stream's draft head; "draft:<stream>" on multi-stream resources)
```

The object body is raw bytes — no JSON, no base64 — sealed with the same
primitive as the envelope above:

```
body           = salt(16) ‖ nonce(12) ‖ AES-256-GCM(HKDF-SHA256(content_key, salt, utf8(info)), nonce, plaintext)
info           = "imgexam-document-version-v1"  (a version)  |  "imgexam-document-draft-v1"  (a draft head)
content_length = len(plaintext) + 44            (declared before sealing; the signed PUT locks it)
```

Vectors: `aes_gcm_envelope.json` (HKDF, wrapKey, encryptContent);
`document_content.json` (a document DEK, its content key, a sealed version,
a sealed draft and both `encrypted_index` summaries — sealed by the web
app's own code).

## Frozen labels

Every HKDF/AAD label below keeps its historical `imgexam-` prefix on
purpose. The name predates `diagnos`, but these strings are wire constants
baked into every ciphertext already stored — renaming one would make
existing data unreadable. Never repurpose a label for a new meaning; a
changed derivation gets a new, separately versioned string (`-v2`) instead.
Code that uses one of these points back here by name — see
`apps/sdk/src/diagnos/crypto/keys.py`, `content.py`, `hybrid.py` and `hkdf.py`.

| Label | Purpose | Section |
|---|---|---|
| `imgexam-sdk-hybrid-seal-v1` | HKDF `info` for the hybrid seal (session and group-key sealing) | §6 |
| `imgexam-patient-dek-v1` | wraps **every** document's DEK (patients, exams, templates) under its security group's key — the web app uses this one label for all three | §7, §8 |
| `imgexam-patient-index-v1` | seals a patient's `encrypted_index` under its DEK | §8 |
| `imgexam-exam-index-v1` | seals an exam's `encrypted_index` | §8 |
| `imgexam-template-index-v1` | seals a report template's `encrypted_index` | §8 |
| `imgexam-document-version-v1` | seals a committed version's body under its content key | §7, §8 |
| `imgexam-document-draft-v1` | seals a draft head's body under its content key | §7, §8 |
| `imgexam-node-dek-v1` | wraps a node's own DEK under its security group's key | §9 |
| `imgexam-node-name-v1` | seals a node's name under its DEK | §9 |
| `\|sse-c-v1` | suffix appended to `security_context.value` to derive a node's SSE-C key | §10 |

## 8. Versioned documents

Patients, exams and report templates share one model: a Firestore **index**
the API exposes (streams of versions, the wrapped DEK, a sealed summary,
clear `meta`) and, per version, a sealed object in R2 the SDK reads and
writes through signed URLs. Only clients ever see plaintext. The external
API serves patients and exams; templates exist only in the web app.

**Streams.** A document has one or more independent streams of versions.
Exams (and templates) have one, `data`. Patients have two: `data` (the
structured record) and `file` (the web editor's rich document, Lexical +
Yjs, not exposed by the SDK). This decides the shape of the version routes:
a multi-stream resource carries `/streams/{stream}`, a single-stream one
does not.

Index (`result.document`, the same shape in every response):
```json
{ "document_id", "workspace_id", "resource": "patients",
  "security_group_id": "sg1",
  "encrypted_keys": { "sg1": <EncryptedPayload> },
  "encrypted_index": <EncryptedPayload>,
  "streams": {
    "data": { "latest_version_id", "versions": [{ "version_id", "size", "created_at", "created_by" }],
              "pending_version_id", "draft"?: { "rev", "size", "updated_at", "updated_by" } },
    "file": { … } },
  "meta"?: { … }, "created_at", "created_by", "updated_at", "updated_by"?, "is_archived", "is_deleted" }
```

A document belongs to **exactly one** security group: sharing a patient
with another team means copying it, never sharing its key.

Keys:
- `dek` = 32 random bytes, one per **document**, shared by every stream and
  version. `encrypted_keys[security_group_id]` =
  `wrapKey(group_key, dek, "imgexam-patient-dek-v1")` — for every resource.
- Each version's body is sealed under its own content key (§7), with
  `key_id = version_id`; a draft head with `key_id = "draft"` (single
  stream) or `"draft:<stream>"` (multi-stream).
- `encrypted_index` = `encryptContent(dek, utf8(json(summary)), "imgexam-<resource>-index-v1")`,
  rewritten with every version, so lists open without downloading one.

Records (JSON before sealing; absent fields are left out):
- `patients` (`data` stream) — `legal_name`, `display_name`,
  `identifiers?: [{ name, value }]` (each `value` is `secret:v1:…`, sealed
  by the vault's sensitive-data route; opening one is audited),
  `external_id?`, `birth_date?`, `biological_sex?`
  (`MALE|FEMALE|INTERSEX|UNDEFINED`), `gender_identity?`, `race_identity?`,
  `email?`, `phone?`, `address?: { postal_code?, street?, number?,
  complement?, district?, city?, state?, country? }`, `internal_notes?:
  string[]`, `custom_attributes?: object`.
- `exams` — `title?`, `modality?`, `exam_date?`, `report_lexical?` (the
  editor's state, the source of truth), `report_html?` (derived from it),
  `custom_attributes?: object`.

Summaries (the plaintext of `encrypted_index`): patients
`{ display_name, legal_name, external_id?, birth_date?, tags: string[] }` —
never identity documents; exams `{ title?, modality?, exam_date? }`.

Dates are UTC ISO 8601 instants (`Date.toISOString()`), truncated to the
workspace's anonymization precision (`month|day|hour|minute|second`) before
sealing.

`meta` (clear, what the vault itself reads): patients `{ specialist_ids? }` ·
exams `{ patient_id, modality?, report_status?, published_at?,
published_by? }` — the web app writes only `patient_id`; everything
clinical stays sealed.

Routes (`{base}` = `/api/external/v1/workspaces/{workspace_id}/{patients|exams}`,
`{s}` = `/streams/{stream}` on patients, empty on exams):
```
GET  {base}?limit=&cursor=&security_group_id=&include_deleted=true    → { items: [index…], next_cursor }
POST {base}   { security_group_id, encrypted_keys, content_length, encrypted_index, stream: "data", meta? }
              → 201 { document, stream, version_id, security_context: { value, kid },
                      upload: { url, method: "PUT", headers: { "content-length", … }, client_headers, expires_at } }
PUT  upload.url                                            (body = sealed object, content-length exactly as signed)
POST {base}/{id}{s}/versions/{version_id}/commit           → { document }        (idempotent on replay)
GET  {base}/{id}?stream=&version_id=                       → { document, stream, version, security_context, download }
POST {base}/{id}{s}/versions   { content_length, encrypted_index?, meta?, expected_latest_version_id? }
              → 201 { staged: true, document, stream, version_id, security_context, upload }   then PUT, then commit
POST {base}/{id}{s}/versions   { is_archived?, is_deleted? }                    (no content_length: patch-only)
              → 200 { staged: false, document }
GET  {base}/{id}{s}/draft                                  → { download, security_context, draft_rev, draft_size, updated_at } | null
PUT  {base}/{id}{s}/draft      { content_length, draft_rev? } → { upload, security_context, draft_rev }   (the web editor's autosave)
```

Rules:
- A change is always a new, complete version; there is no partial update.
  Archive and delete are flags set by a patch-only reservation — no new
  version, no upload — and delete is never a hard delete.
- One pending version per stream: a second reservation answers
  `409 DocumentVersionPending` until the first is committed or expires
  (retry briefly). `expected_latest_version_id` answers
  `409 DocumentVersionMismatch` when another version was committed since.
  A commit before the object was uploaded answers `400 DocumentObjectNotFound`.
- Reading: the draft head wins when it exists and its `updated_at` is later
  than the latest version's `created_at`; otherwise the latest version wins
  (a commit does not erase the draft, it supersedes it).
- The vault lists SSE-C headers next to document URLs, but the web app does
  not use SSE-C on documents — neither on the `PUT` nor on the `GET` — so
  the SDK sends only the signed `content-length` and reads with a plain
  `GET`. A second layer only one side sent would make the object unreadable
  to the other.

## 9. Files and folders (nodes)

Every file (DICOM, image, video, PDF) and every folder of a workspace is a
**node** under `{base}` = `/api/external/v1/workspaces/{workspace_id}/nodes`.
A node belongs to one security group; reading one needs only its id — the
vault authorizes against the group the node itself declares.

Keys, as the web app's upload pipeline (`@repo/magic-files`) builds them:
```
node_dek       = random(32)                                          (one per node, file or folder)
encrypted_keys = { <security_group_id>: wrapKey(group_key, node_dek, "imgexam-node-dek-v1") }
encrypted_name = encryptContent(node_dek, utf8(name), "imgexam-node-name-v1")
content_key    = HKDF-SHA256(ikm = node_dek, salt = utf8(node_id), info = utf8(security_context.value), L = 32)
```
The content key is the documents' derivation (§7) with `key_id = node_id` —
the vault also returns that id as `version_id`, since nodes are not
versioned. `security_context` comes back at staging, before the first byte
is sealed, and again next to every download URL. The name is whatever the
uploader chose: the web app seals a relative path (`exams/2024/IM-0001.dcm`),
so a reader must never use it as a local path as-is.

Body (`secretstream.json`, `node_content.json`): libsodium
`crypto_secretstream_xchacha20poly1305` under `content_key`, framed as
`header(24) ‖ (len_u32_be ‖ frame)*`. The plaintext goes in 1 MiB
(`1048576`) chunks, every full chunk as a plain message; the tail —
**empty when the size is an exact multiple** — always goes last, as its own
`TAG_FINAL` frame. So, for `n` plaintext bytes:

```
size = 24 + (⌊n / 1048576⌋ + 1) × (4 + 17) + n
```

`size` is declared at staging and the vault signs the `PUT` for exactly that
many bytes, so it is computed before encrypting; the vault also charges the
workspace by it. A multipart upload cuts the framed byte stream at fixed
offsets (`part_size`), never at frame boundaries.

Routes:
```
POST {base}/uploads   { security_group_id, exam_id?, parent_id?, files: [entry] (≤ 100) }
     entry = { client_ref (≤ 64 chars), encrypted_name, encrypted_keys, size, mime_type? }      a file
           | { kind: "folder", client_ref, encrypted_name, encrypted_keys }                     a folder
  → 201 { items: [{ client_ref, node_id, version_id, security_context, kind,
                    mode?: "single" | "multipart", upload?, part_size?, part_count?, upload_id? }] }
PUT  upload.url   with upload.headers + SSE-C (§10)                           single: size ≤ 64 MiB
POST {base}/uploads/complete             { node_ids (≤ 200) } → { ready: [node…], missing: [node_id…] }
POST {base}/{node_id}/multipart                               → { upload_id, part_size (32 MiB), part_count }
POST {base}/{node_id}/multipart/parts    { part_numbers (≤ 200) } → { parts: [{ part_number, url, expires_at }] }
PUT  part.url     with SSE-C (§10); the ETag comes back as a response header
POST {base}/{node_id}/multipart/complete { parts: [{ part_number, etag }] } → { node }
POST {base}/{node_id}/multipart/abort                         → { aborted: true }
GET  {base}?security_group_id=&exam_id=&parent_id=&include_pending=&limit=&cursor=   → { items: [node…], next_cursor }
GET  {base}/{node_id}                                         → { node, security_context, download }
```

- **Idempotent staging.** The vault deduplicates a reservation by
  `(workspace, client_ref)`: re-sending the same ref (same caller, same
  group, still pending) returns the same node and charges once. A client
  draws one ref per file and reuses it when it retries.
- **Folders** are ready at once — there is no content to upload. `parent_id`
  must be a ready folder of the same group.
- **Small files** (≤ 64 MiB) go up in one signed `PUT` each and are
  confirmed together; `missing` names the nodes whose object never arrived.
- **Large files** go up in parts. Staging usually opens the multipart
  upload already (`upload_id`); only when it did not does the client call
  `{node_id}/multipart`. An aborted upload leaves the node `failed`; an
  abandoned reservation expires after 6 h.
- **Reads.** `GET {base}/{node_id}` answers `404` for a folder or an
  unfinished upload — there is nothing to download. A list shows only ready
  nodes unless `include_pending=true`.

## 10. SSE-C

R2's server-side encryption with a customer key is a second layer on top of
the end-to-end encryption of §9; the vault never sees the key. The web app
derives it as the content key's sister and sends it on the single `PUT`, on
every multipart part and on the `GET` — an object written with SSE-C can
only be read with the same key:

```
sse_c_key = HKDF-SHA256(ikm = node_dek, salt = utf8(node_id), info = utf8(security_context.value ‖ "|sse-c-v1"), L = 32)
x-amz-server-side-encryption-customer-algorithm: AES256
x-amz-server-side-encryption-customer-key:       base64(sse_c_key)            (standard base64, with padding)
x-amz-server-side-encryption-customer-key-md5:   base64(MD5(sse_c_key))
```

`upload.headers` and `download.headers` carry the values the vault fixes
(`content-length`, `content-type`, the algorithm) and must be sent as they
came; `client_headers` names the two whose values only the client knows.
Versioned documents (§8) do not use SSE-C. The vault-side questions still
open about this layer are listed in [COMPATIBILITY.md](COMPATIBILITY.md).

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
| `ValidationError`, `DocumentTooLarge`, `DocumentObjectNotFound`, `DriveBatchTooLarge`, `DriveDuplicateClientRef`, `DriveFileTooLarge`, `DriveInvalidParent`, `DriveObjectNotFound` | 400 | `ValidationError` |
| `Unauthorized`, `SessionNotFound`, `SignatureInvalid`, `SignatureMissing` | 401 | `AuthenticationError` (session gone → re-enroll) |
| `SignatureTimestampSkew` | 401 | resync clock, retry once, then `AuthenticationError` |
| `QuotaExceeded`, `BudgetNotProvisioned` | 402 | `QuotaError` |
| `ServiceAccountRevoked`, `DocumentAccessDenied`, `InsufficientPermission`, `NotAWorkspaceMember`, `DriveUploadNotOwned` | 403 | `DiagnosPermissionError` |
| `DocumentNotFound`, `DocumentVersionNotFound`, `DriveNodeNotFound`, `SdkEnrollmentNotFound`, `NotFound` | 404 | `NotFoundError` |
| `DocumentVersionPending`, `DocumentVersionNotPending`, `DocumentVersionMismatch`, `DocumentDraftMismatch`, `ReplayDetected`, `DriveNodeNotPending`, `UploadIncomplete` | 409 | `ConflictError` (`ReplayDetected` is retried once with a new nonce; `DocumentVersionPending` on a reservation is retried after 1.5 s and 3 s) |
| `RateLimitExceeded` | 429 | `RateLimitError` (honour `Retry-After` if present; else a jittered backoff, up to 3 retries) |
| `RequestBodyTooLarge` | 413 | `ValidationError` |
| 5xx / `InternalServerError`, `MultipartUploadFailed` | 5xx | `VaultError` (carries `trace_id`; one retry after a fixed backoff) |

A response that is not valid JSON at all (a proxy's error page, a truncated
body) never carries a `code`; the SDK raises `VaultError` with the synthetic
code `InvalidResponse` instead of leaking a bare parse error. `SessionExpiredError`
is a purely local error — the SDK has no live session to sign with — and
never comes from a vault response. `ProtocolError` is raised when a
well-formed answer breaks the protocol (a signed size that is not the
sealed body's, a version reservation answered as patch-only, a storage part
without an ETag). `UploadIncomplete` is raised by the SDK, not the vault:
`uploads/complete` listed a node as `missing`, so its `PUT` never landed —
upload that file again. A commit that fails on the network or with a 5xx is
replayed with backoff (0.5 s, 1 s): commits are idempotent. A multipart
upload that fails midway is aborted before the error is raised.

## 13. Limits

API body 1 MiB · document version ≤ 64 MiB · file ≤ 50 GiB · ≤ 100 files per reservation · ≤ 200 node ids per confirmation · single `PUT` ≤ 64 MiB · multipart part 32 MiB, ≤ 200 part URLs per call · list page ≤ 200 · a pending upload expires after 6 h, its signed URLs after 1 h.
