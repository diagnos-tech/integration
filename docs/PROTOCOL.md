# PROTOCOL — the contract between the SDK and the vault · o contrato entre o SDK e o cofre

🇺🇸 Normative. Every format below is pinned by `sdk/tests/vectors/*.json`,
generated from the vault's own TypeScript (`apps/server/scripts/generateIntegrationVectors.ts`).
When this document and a vector disagree, the vector wins and this document
has a bug.
🇧🇷 Normativo. Todo formato abaixo está travado por `sdk/tests/vectors/*.json`,
gerados do próprio TypeScript do cofre. Quando este documento e um vetor
discordarem, o vetor vence e este documento tem um bug.

## 0. Conventions · Convenções

- 🇺🇸 `b64url` = RFC 4648 §5 **without padding**. `hex` = lowercase. JSON is
  UTF-8. Ids are opaque strings. Time: `expires_at`/`*_at` **numbers** are
  Unix seconds (`_ms` = milliseconds); `created_at`/`updated_at`/`completed_at`
  on indexes and nodes are ISO-8601 **strings**.
  🇧🇷 `b64url` = RFC 4648 §5 **sem padding**. `hex` = minúsculo. JSON é UTF-8.
  Ids são strings opacas. Tempo: `expires_at`/`*_at` **numéricos** são segundos
  Unix (`_ms` = milissegundos); `created_at`/`updated_at`/`completed_at` em
  índices e nós são **strings** ISO-8601.
- 🇺🇸 Base URL: `https://vault.diagnos.health`. SDK audience: `/api/external/v1`.
  🇧🇷 Base: `https://vault.diagnos.health`. Audiência do SDK: `/api/external/v1`.
- 🇺🇸 Every response is an envelope:
  🇧🇷 Toda resposta é um envelope:
  ```json
  { "success": true,  "status": "success", "status_code": 200, "result": {…}, "docs": "https://vault.diagnos.health/docs" }
  { "success": false, "status": "fail",    "status_code": 4xx, "errors": [{ "code": "QuotaExceeded", "message": "…", "trace_id": null }], "docs": "…" }
  ```
  🇺🇸 Decide by `code`, never by `message`. `X-Request-Id` is on every response.
  🇧🇷 Decida por `code`, nunca por `message`. `X-Request-Id` vem em toda resposta.

## 1. Identity · Identidade

🇺🇸 `DIAGNOS_API_TOKEN` is `apikey-<JWT EdDSA>` issued by a workspace admin.
Claims: `sub` (key id, rotatable), `account_id`, `workspace_id`, `name`
(`slug@<workspace_id>.diagnos.health`), `iss = api.diagnos.health`, no `exp`. The
SDK reads `workspace_id` from the payload **without verifying** — only to
build URLs; the vault is the verifier. Revocation is server-side and shows
up as `403 ServiceAccountRevoked`.
🇧🇷 `DIAGNOS_API_TOKEN` é `apikey-<JWT EdDSA>` emitido por um admin. Claims:
`sub` (id da chave, rotacionável), `account_id`, `workspace_id`, `name`,
`iss = api.diagnos.health`, sem `exp`. O SDK lê `workspace_id` do payload **sem
verificar** — só para montar URLs; quem verifica é o cofre. Revogação é do
lado do servidor e aparece como `403 ServiceAccountRevoked`.

Header on every request · Header em toda requisição: `Authorization: Bearer apikey-<jwt>`.

## 2. Clock · Relógio

🇺🇸 Signatures carry a timestamp the vault checks within ±120 s of its own
clock. Before the first signed request: `POST /time` with body `{"id": 1}`
→ `{"id": 1, "result": <server_ms>}` (raw, not enveloped). Offset =
`server_ms − local_ms`; take the median of three round-trips. On
`401 SignatureTimestampSkew`, resync and retry once.
🇧🇷 Assinaturas levam um timestamp que o cofre confere dentro de ±120 s do
relógio dele. Antes da primeira requisição assinada: `POST /time` com corpo
`{"id": 1}` → `{"id": 1, "result": <ms_do_servidor>}` (cru, sem envelope).
Offset = `ms_servidor − ms_local`; use a mediana de três idas e voltas. Em
`401 SignatureTimestampSkew`, ressincronize e tente uma vez.

## 3. Request signature · Assinatura da requisição

🇺🇸 Every request except `/time`, `session/registry` (POST and GET poll)
carries three headers:
🇧🇷 Toda requisição exceto `/time`, `session/registry` (POST e GET do poll)
leva três headers:

```
X-Signature-Timestamp: <unix seconds, decimal, server clock>
X-Signature-Nonce:     <≥16 random bytes, b64url; unique per request>
X-Signature-Hmac:      <hex(HMAC-SHA512(sign_key, canonical))>
```

🇺🇸 `canonical` is six fields joined by `\n` (0x0A), encoded as UTF-8:
🇧🇷 `canonical` são seis campos unidos por `\n` (0x0A), em UTF-8:

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

🇺🇸 A `(timestamp, nonce)` pair is single-use: the vault answers
`409 ReplayDetected` to a byte-identical resend. Retries generate a new pair.
🇧🇷 O par `(timestamp, nonce)` é de uso único: o cofre responde
`409 ReplayDetected` a um reenvio idêntico. Retentativas geram um par novo.

Vector · Vetor: `request_signature.json`.

## 4. Session keys and the response seed · Chaves de sessão e a semente

🇺🇸 A session is `session_id`, `sign_key` (32 B, HMAC) and `enc_key` (32 B,
AES-256-GCM), valid until `expires_at`. Every signed response carries
`X-Session-Seed: <nonce b64url>.<ciphertext b64url>` = AES-256-GCM(`enc_key`,
iv = nonce 12 B, AAD = UTF-8(`session_id`)) over the JSON `{"seed": "<32 B b64url>"}`.
The SDK mixes it into its own entropy — `SHA-256(os.urandom(32) ‖ state ‖ counter)`,
`state = SHA-256(seed)` — for nonces and keys it generates next. It never
*replaces* the OS RNG. The reference SDK opens, parses and decodes the seed
inside its memory enclave; it never exists as a Python object.
🇧🇷 Uma sessão é `session_id`, `sign_key` (32 B, HMAC) e `enc_key` (32 B,
AES-256-GCM), válida até `expires_at`. Toda resposta assinada leva
`X-Session-Seed: <nonce b64url>.<ciphertext b64url>` = AES-256-GCM(`enc_key`,
iv = nonce 12 B, AAD = UTF-8(`session_id`)) sobre o JSON `{"seed": "<32 B b64url>"}`.
O SDK mistura a semente à própria entropia — `SHA-256(os.urandom(32) ‖ estado ‖ contador)`,
`estado = SHA-256(semente)` — para os próximos nonces e chaves. Nunca
*substitui* o RNG do SO. O SDK de referência abre, lê e decodifica a semente
dentro do enclave de memória; ela nunca existe como objeto Python.

## 5. Enrollment · Enrollment

```
POST /api/external/v1/workspaces/{workspace_id}/session/registry      (Bearer only, unsigned)
{ "public_keys": { "x25519": "<32 B b64url>", "mlkem768": "<1184 B b64url>" },
  "runtime": { "sdk_name": "diagnos-python", "sdk_version": "0.1.0", "language": "python 3.12",
               "os": "linux", "arch": "x86_64", "hostname"?: "…", "user"?: "…",
               "container": true, "cloud"?: "aws" } }
→ 201 { "enrollment_id", "code": "123456", "approval_url", "expires_at", "poll_interval_seconds" }
```

🇺🇸 Print `approval_url` and `code` to the terminal. A workspace admin opens
the link, reads the runtime description, types the code and picks security
groups. Poll every `poll_interval_seconds` until `expires_at`:
🇧🇷 Imprima `approval_url` e `code` no terminal. Um admin abre o link, lê a
descrição, digita o código e escolhe grupos. Faça poll a cada
`poll_interval_seconds` até `expires_at`:

```
GET /api/external/v1/workspaces/{workspace_id}/session/registry/{enrollment_id}   (Bearer only)
→ { "status": "pending" } | { "status": "denied" }
  | { "status": "approved", "approval": { "session_id", "session_expires_at",
        "sealed_session": <HybridSeal>, "sealed_group_keys": { "<security_group_id>": <HybridSeal>, … } } }
```

- 🇺🇸 `sealed_session` opens (AAD = `enrollment_id`) to the JSON
  `{"session_id","sign_key":"<32 B b64url>","enc_key":"<32 B b64url>","expires_at"}`.
  🇧🇷 `sealed_session` abre (AAD = `enrollment_id`) para o JSON acima.
- 🇺🇸 Each `sealed_group_keys[sg]` opens (AAD = `enrollment_id`) to the **raw
  32-byte DEK** of that security group — not JSON, not base64.
  🇧🇷 Cada `sealed_group_keys[sg]` abre (AAD = `enrollment_id`) para a **DEK
  crua de 32 bytes** daquele grupo — não JSON, não base64.
- 🇺🇸 `POST /api/external/v1/session/lock` (signed, no body) ends the session.
  🇧🇷 `POST /api/external/v1/session/lock` (assinado, sem corpo) encerra a sessão.

## 6. HybridSeal — X25519 + ML-KEM-768 · Selo híbrido

🇺🇸 The same construction seals the session (vault → SDK) and the group DEKs
(web app → SDK). Reference: `apps/server/src/services/sdk/hybridSeal.ts`.
🇧🇷 A mesma construção sela a sessão (cofre → SDK) e as DEKs (app web → SDK).

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

🇺🇸 Opening: split `salt` into `eph.public[0:32]` and `kem_ct[32:]`, derive
`ss1 = X25519(sk.x25519, eph.public)` and `ss2 = ML-KEM-768.decaps(sk.mlkem768, kem_ct)`,
same HKDF, AES-GCM decrypt. Both secrets must be present: the design survives
either primitive being broken alone.
🇧🇷 Abertura: separe `salt` em `eph.public[0:32]` e `kem_ct[32:]`, derive os
dois segredos, mesmo HKDF, decifre. Os dois segredos são necessários: o
desenho sobrevive a qualquer uma das primitivas cair sozinha.

Vector · Vetor: `hybrid_seal.json` (contains the recipient secret keys).

## 7. Key and content envelope · Envelope de chave e de conteúdo

🇺🇸 `EncryptedKeyPayload` (`{salt, nonce, ciphertext}`, all b64url) is the one
symmetric envelope of the product. Reference:
`packages/core/utils/_aesGcmEnvelope.ts`.
🇧🇷 `EncryptedKeyPayload` (`{salt, nonce, ciphertext}`, tudo b64url) é o único
envelope simétrico do produto.

```
salt     = random(16)
derived  = HKDF-SHA256(ikm = wrapping_key, salt = salt, info = utf8(info), L = 32)
nonce    = random(12)
ct       = AES-256-GCM(derived, nonce, plaintext, aad = ∅)          (tag appended)
```

🇺🇸 `wrapKey` (plaintext is a key) and `encryptContent` (plaintext is data)
are the same bytes; only `info` changes. `info` strings are versioned and
never shared between purposes:
🇧🇷 `wrapKey` (o plaintext é uma chave) e `encryptContent` (o plaintext é dado)
são os mesmos bytes; só `info` muda. As strings de `info` são versionadas e
nunca compartilhadas entre propósitos:

| Purpose · Propósito | `info` |
|---|---|
| document DEK wrapped by a group DEK · DEK do documento embrulhada pela DEK do grupo | `imgexam-patient-dek-v1` · `imgexam-exam-dek-v1` · `imgexam-template-dek-v1` |
| document content · conteúdo do documento | `imgexam-patient-record-v1` · `imgexam-exam-record-v1` · `imgexam-template-record-v1` |
| drive node name, wrapped with the group DEK · nome do arquivo, embrulhado com a DEK do grupo | `imgexam-drive-node-name-v1` |

Vector · Vetor: `aes_gcm_envelope.json` (HKDF, wrapKey, encryptContent).

## 8. Versioned documents · Documentos versionados

🇺🇸 Patients, exams and templates share one model: a Firestore **index** the
API exposes (versions, latest, groups, wrapped keys, clear `meta`) and, per
version, an encrypted object in R2 the SDK reads/writes through signed URLs.
Only the SDK ever sees plaintext.
🇧🇷 Pacientes, exames e modelos compartilham um modelo: um **índice** que a
API expõe (versões, mais recente, grupos, chaves embrulhadas, `meta` em
claro) e, por versão, um objeto cifrado no R2 que o SDK lê/escreve por URL
assinada. Só o SDK vê texto claro.

Index · Índice (`result.document`):
```json
{ "document_id", "workspace_id", "resource": "patients", "security_groups": ["sg1"],
  "encrypted_keys": { "sg1": <EncryptedKeyPayload> }, "latest_version_id", "versions": [{ "version_id", "size", "created_at", "created_by" }],
  "pending_version_id", "meta": {…}, "created_at", "created_by", "updated_at", "updated_by", "is_archived", "is_deleted" }
```

Keys · Chaves:
- 🇺🇸 `doc_dek` = 32 random bytes, one per **document** (versions reuse it).
  `encrypted_keys[sg]` = `wrapKey(group_dek[sg], doc_dek, "diagnos-<singular>-dek-v1")`.
  🇧🇷 `doc_dek` = 32 bytes aleatórios, uma por **documento** (as versões reusam).
- 🇺🇸 Object body = UTF-8 JSON of `encryptContent(doc_dek, utf8(json(record)), "diagnos-<singular>-record-v1")`,
  i.e. `{"salt":…,"nonce":…,"ciphertext":…}`. `Content-Type: application/json`.
  🇧🇷 Corpo do objeto = JSON UTF-8 de `encryptContent(...)`, i.e. `{"salt","nonce","ciphertext"}`.

Records · Registros (JSON before encryption · JSON antes de cifrar):
- `patients` — mirrors `@repo/core/schemas/Patient.ts#PatientRecord`:
  `legal_name`, `display_name`, `legal_id?`, `external_id?`, `birth_date?` (ISO date),
  `biological_sex?` (`MALE|FEMALE|INTERSEX|UNDEFINED`), `gender_identity?`, `race_identity?`,
  `internal_notes?: string[]`, `email?`, `phone?`, `custom_attributes?: object`.
- `exams` — `title?`, `description?`, `report?: { format: "html"|"markdown"|"text", content }`, `custom_attributes?: object`.
- `templates` — `title`, `content_html`, `category?`. (🇺🇸 web client only · 🇧🇷 só client web)

`meta` (clear · em claro): patients `{ specialist_ids? }` · exams `{ patient_id, modality?, report_status?, dicom_manifest_status?, … }` · templates `{ category? }`.

Routes · Rotas (`{base}` = `/api/external/v1/workspaces/{workspace_id}/{resource}`):
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

🇺🇸 There is no partial update and no delete: a change is a new full
version; archival/deletion are flags on the index set through a new version.
Only the principal that staged a version may commit it.
🇧🇷 Não existe atualização parcial nem apagar: mudança é uma versão nova e
inteira; arquivar/apagar são flags do índice gravadas por uma versão nova. Só
quem reservou a versão a confirma.

## 9. Drives (files) · Drives (arquivos)

🇺🇸 A drive is a security group. Any file (DICOM, image, video, PDF) is a
**node** in `{base}` = `/api/external/v1/workspaces/{workspace_id}/drives/{security_group_id}`.
🇧🇷 Um drive é um security group. Todo arquivo é um **nó** em `{base}`.

Keys · Chaves:
```
node_key       = HKDF-SHA256(ikm = group_dek, salt = utf8(node_id), info = utf8("imgexam-drive-node-key-v1"), L = 32)
encrypted_name = wrapKey(group_dek, utf8(original_file_name), "imgexam-drive-node-name-v1")
```
🇺🇸 Deriving the content key from the group DEK means a node needs no wrapped
key of its own and revocation happens at the group. The name is wrapped with
the **group DEK** (not the node key) because it travels in the staging request,
before the vault has assigned a `node_id`.
🇧🇷 Derivar a chave do conteúdo da DEK do grupo dispensa chave embrulhada por
nó; revogação é no grupo. O nome é embrulhado com a **DEK do grupo** (não com a
chave do nó) porque viaja no pedido de reserva, antes de o cofre atribuir um
`node_id`.

Body · Corpo (`secretstream.json`): libsodium `crypto_secretstream_xchacha20poly1305` with `node_key`,
framed as `[header 24 B][len uint32 BE][cipher chunk]*`; plaintext chunks of
1 MiB (`1048576`), last chunk pushed with `TAG_FINAL` (an empty file still has one final chunk).
🇺🇸 The reader re-assembles frames by length before pulling; parts of a multipart
upload split the framed byte stream at arbitrary offsets.
🇧🇷 O leitor remonta os frames pelo comprimento antes de abrir; as partes de um
multipart cortam o stream framed em offsets arbitrários.

Routes · Rotas:
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

🇺🇸 `size` is the size of the **encrypted, framed** body — compute it before
uploading (24 + Σ(4 + chunk + 17)). The vault charges the workspace by it.
🇧🇷 `size` é o tamanho do corpo **cifrado e framed** — calcule antes de subir
(24 + Σ(4 + chunk + 17)). O cofre cobra o workspace por ele.

## 10. SSE-C (opt-in) · SSE-C (opcional)

🇺🇸 Objects are already end-to-end encrypted. Additionally, single PUT/GET
may use R2's SSE-C with a key the vault never sees. Disabled by default until
the web client adopts it (`DIAGNOS_SSE_C=1` enables); never used for multipart
(the vault creates that upload and must not hold the key).
🇧🇷 Os objetos já são cifrados de ponta a ponta. Adicionalmente, PUT/GET
único pode usar SSE-C do R2 com chave que o cofre nunca vê. Desligado por
padrão até o client web adotar (`DIAGNOS_SSE_C=1` liga); nunca em multipart.

```
sse_key = HKDF-SHA256(ikm = doc_dek | node_key, salt = ∅, info = utf8("imgexam-sse-c-v1"), L = 32)
x-amz-server-side-encryption-customer-algorithm: AES256
x-amz-server-side-encryption-customer-key:       base64(sse_key)         (standard base64, with padding)
x-amz-server-side-encryption-customer-key-MD5:   base64(MD5(sse_key))
```

## 11. OpenBao auto-unseal · Auto-unseal com OpenBao

🇺🇸 Optional. When `OPENBAO_ADDR` and `OPENBAO_TOKEN` are set, the SDK saves
its unlocked state after a successful enrollment and restores it on start,
so a restart needs no human. This deliberately moves the group DEKs from RAM
to OpenBao's encrypted storage: whoever can read that path can read the
workspace. Scope the token to the path.
🇧🇷 Opcional. Com `OPENBAO_ADDR` e `OPENBAO_TOKEN`, o SDK salva o estado
desbloqueado depois de um enrollment e o restaura ao subir, sem humano. Isso
move deliberadamente as DEKs da RAM para o armazenamento cifrado do OpenBao:
quem lê aquele path lê o workspace. Restrinja o token ao path.

KV v2 · `mount = OPENBAO_MOUNT (default "secret")`, path `OPENBAO_PATH_PREFIX (default "diagnos")/{workspace_id}/{account_id}`:
```json
{ "v": 1, "enrollment_id", "x25519_secret", "mlkem768_secret", "session_id", "sign_key", "enc_key",
  "session_expires_at", "group_keys": { "<sg>": "<32 B b64url>" }, "saved_at" }
```
🇺🇸 Restore only while `session_expires_at − now > 60 s`; otherwise enroll again.
🇧🇷 Restaure só enquanto `session_expires_at − agora > 60 s`; senão, novo enrollment.

🇺🇸 `OPENBAO_TOKEN_FILE` may name a file holding the token instead of `OPENBAO_TOKEN`
(the form container orchestrators prefer). Writing this document is the one
moment the reference SDK's keys leave locked memory: they are revealed into
buffers that are zeroed right after the request is built.
🇧🇷 `OPENBAO_TOKEN_FILE` pode nomear um arquivo com o token em vez de `OPENBAO_TOKEN`
(a forma que orquestradores de container preferem). Escrever este documento é
o único momento em que as chaves do SDK de referência saem da memória travada:
são reveladas em buffers zerados logo depois de a requisição ser montada.

## 12. Errors · Erros

| `code` | HTTP | SDK exception |
|---|---|---|
| `ValidationError` | 400 | `ValidationError` |
| `Unauthorized`, `SessionNotFound`, `SignatureInvalid`, `SignatureMissing` | 401 | `AuthenticationError` (session gone → re-enroll) |
| `SignatureTimestampSkew` | 401 | resync clock, retry once, then `AuthenticationError` |
| `QuotaExceeded`, `BudgetNotProvisioned` | 402 | `QuotaError` |
| `ServiceAccountRevoked`, `DocumentAccessDenied`, `InsufficientPermission`, `NotAWorkspaceMember` | 403 | `PermissionError` (`DiagnosPermissionError`) |
| `DocumentNotFound`, `DocumentVersionNotFound`, `DriveNodeNotFound`, `SdkEnrollmentNotFound`, `NotFound` | 404 | `NotFoundError` |
| `DocumentVersionPending`, `DocumentVersionNotPending`, `ReplayDetected`, `DriveNodeNotPending` | 409 | `ConflictError` (`ReplayDetected` is retried with a new nonce) |
| `RateLimitExceeded` | 429 | `RateLimitError` (honour `Retry-After` if present; else backoff) |
| `RequestBodyTooLarge` | 413 | `ValidationError` |
| 5xx / `InternalServerError` | 5xx | `VaultError` (carries `trace_id`) |

## 13. Limits · Limites

API body 1 MiB · document version ≤ 64 MiB · batch ≤ 1000 files · single file ≤ 64 MiB · multipart part 32 MiB, ≤ 200 part URLs per call · list page ≤ 200.
