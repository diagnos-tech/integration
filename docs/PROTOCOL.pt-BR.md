# PROTOCOL — o contrato entre o SDK e o cofre

[English](PROTOCOL.md) · **Português (Brasil)**

Normativo. Todo formato abaixo está travado por `apps/sdk/tests/vectors/*.json`,
gerados a partir da implementação de referência do cofre. Quando este
documento e um vetor discordarem, o vetor vence e este documento tem um bug.

> [!NOTE]
> As seções [8](#8-documentos-versionados) e [9](#9-drives-arquivos)
> descrevem a implementação 0.1 do SDK `diagnos` para pacientes, exames e
> arquivos de drive, anterior à revisão atual do protocolo do cofre. Veja
> [COMPATIBILITY.pt-BR.md](COMPATIBILITY.pt-BR.md) para o que é e o que não
> é compatível com `vault.diagnos.health` hoje. O resto deste documento —
> convenções, identidade, relógio, assinatura, chaves de sessão e a semente
> da resposta, enrollment, o selo híbrido, rótulos congelados, SSE-C,
> auto-unseal com OpenBao, erros e limites — é fiel ao cofre como ele roda
> hoje.

## 0. Convenções

- `b64url` = RFC 4648 §5 **sem padding**. `hex` = minúsculo. JSON é UTF-8.
  Ids são strings opacas. Tempo: `expires_at`/`*_at` **numéricos** são
  segundos Unix (`_ms` = milissegundos); `created_at`/`updated_at`/`completed_at`
  em índices e nós são **strings** ISO-8601.
- Base: `https://vault.diagnos.health`. Audiência do SDK: `/api/external/v1`.
- Toda resposta é um envelope:
  ```json
  { "success": true,  "status": "success", "status_code": 200, "result": {…}, "docs": "https://vault.diagnos.health/docs" }
  { "success": false, "status": "fail",    "status_code": 4xx, "errors": [{ "code": "QuotaExceeded", "message": "…", "trace_id": null }], "docs": "…" }
  ```
  Decida por `code`, nunca por `message`. `X-Request-Id` vem em toda
  resposta. `GET /time` (§2) é a única exceção: responde um `{"result": …}`
  cru, sem envelope.

## 1. Identidade

`DIAGNOS_API_TOKEN` é `apikey-<JWT EdDSA>`, emitido por um admin do
workspace. Claims que o SDK lê: `sub` (id da chave, rotacionável),
`account_id`, `workspace_id`, `name` (`slug@<workspace_id>.diagnos.health`).
O token também carrega `iss`, o emissor do cofre — não conferido pelo SDK,
já que o SDK nunca verifica a assinatura do JWT: ele não tem a chave para
isso, e só o cofre a tem. `workspace_id` é lido do payload só para montar
URLs; não há claim `exp`, e a revogação é do lado do servidor, aparecendo
como `403 ServiceAccountRevoked` na próxima chamada assinada.

Header em toda requisição: `Authorization: Bearer apikey-<jwt>`.

## 2. Relógio

Assinaturas levam um timestamp que o cofre confere dentro de ±120 s do
relógio dele. Antes da primeira requisição assinada: `GET /time`, sem auth,
sem envelope → `{"result": <ms_do_servidor>}`. Offset = `ms_servidor −
ms_local`; use a mediana de três idas e voltas. Em `401
SignatureTimestampSkew`, ressincronize e tente uma vez.

## 3. Assinatura da requisição

Toda requisição exceto `GET /time` e `session/registry` (tanto o `POST`
quanto o `GET` do poll) leva três headers:

```
X-Signature-Timestamp: <segundos unix, decimal, relógio do servidor>
X-Signature-Nonce:     <≥16 bytes aleatórios, b64url; único por requisição>
X-Signature-Hmac:      <hex(HMAC-SHA512(sign_key, canonical))>
```

`canonical` são seis campos unidos por `\n` (0x0A), em UTF-8:

```
METHOD \n PATH \n QUERY \n TIMESTAMP \n NONCE \n sha256hex(BODY)
```

1. `METHOD` maiúsculo ASCII.
2. `PATH` exatamente como enviado no fio, percent-encoded, **nunca
   decodificado** (`/api/external/v1/workspaces/ws%201/patients`).
3. `QUERY` sem `?`; divida em `&`, ordene os pares `k=v` crus por ponto de
   código, junte com `&`; string vazia quando não há query.
4. `TIMESTAMP` o texto exato do header.
5. `NONCE` o texto exato do header.
6. SHA-256 em hex dos bytes crus do corpo; corpo vazio vira o hash da
   string vazia (`e3b0c442…b855`).

Um par `(timestamp, nonce)` é de uso único: o cofre responde
`409 ReplayDetected` a um reenvio idêntico. Retentativas geram um par novo.

Vetor: `request_signature.json`.

## 4. Chaves de sessão e a semente da resposta

Uma sessão é `session_id`, `sign_key` (32 B, HMAC) e `enc_key` (32 B,
AES-256-GCM), válida até `expires_at`.

Toda resposta a uma requisição assinada leva `random_seed` no envelope
JSON:

```json
{ "random_seed": { "nonce": "<b64url>", "ciphertext": "<b64url>" }, "result": {…}, … }
```

`random_seed` = AES-256-GCM(`enc_key`, iv = `nonce` (12 B), AAD =
UTF-8(`session_id`)) sobre o JSON `{"seed": "<32 B b64url>"}`. Ela viaja no
corpo, não num header, para ficar fora de log de proxy e de trace de APM,
que registram headers com muito mais frequência que corpos.

O SDK mistura a semente à própria entropia em vez de confiar nela sozinha:

```
estado = SHA-256(semente)
bloco  = SHA-256(os_random(32) ‖ estado ‖ contador)   # contador reinicia em 0 a cada semente nova
```

`os_random(32)` sempre domina cada bloco, então uma semente de puros zeros
degrada graciosamente para aleatoriedade pura do SO, nunca para algo mais
fraco — a semente aumenta o `os.urandom`, nunca o substitui. O SDK de
referência abre, lê e decodifica `random_seed` dentro do enclave de memória
(`apps/sdk/native/README.pt-BR.md`); ela nunca existe como objeto Python.

O cofre também aceita um campo `random_seed` opcional, contribuído pelo
cliente, no próprio corpo de uma requisição assinada, para o SDK devolver
entropia. Este SDK ainda não manda um — só consome o do cofre.

Vetor: `aes_gcm_envelope.json` cobre o AEAD; `hybrid_seal.json` cobre o selo
que entrega `sign_key`/`enc_key` em primeiro lugar (§6).

## 5. Enrollment

```
POST /api/external/v1/workspaces/{workspace_id}/session/registry      (só Bearer, sem assinatura)
{ "public_keys": { "x25519": "<32 B b64url>", "mlkem768": "<1184 B b64url>" },
  "runtime": { "sdk_name": "diagnos-python", "sdk_version": "0.1.0", "language": "python 3.12",
               "os": "linux", "arch": "x86_64", "hostname"?: "…", "user"?: "…",
               "container": true, "cloud"?: "aws" } }
→ 201 { "enrollment_id", "code": "123456", "approval_url", "expires_at", "poll_interval_seconds" }
```

Imprima `approval_url` e `code` no terminal. Um admin do workspace abre o
link, lê a descrição do runtime, digita o código e escolhe os security
groups. Faça poll a cada `poll_interval_seconds` até `expires_at`:

```
GET /api/external/v1/workspaces/{workspace_id}/session/registry/{enrollment_id}   (só Bearer)
→ { "status": "pending" } | { "status": "denied" }
  | { "status": "approved", "approval": { "session_id", "session_expires_at",
        "sealed_session": <HybridSeal>, "sealed_group_keys": { "<security_group_id>": <HybridSeal>, … } } }
```

- `sealed_session` abre (AAD = `enrollment_id`) para o JSON
  `{"session_id","sign_key":"<32 B b64url>","enc_key":"<32 B b64url>","expires_at"}`.
- Cada `sealed_group_keys[sg]` abre (AAD = `enrollment_id`) para a **DEK
  crua de 32 bytes** daquele security group — não JSON, não base64.
- `POST /api/external/v1/session/lock` (assinado, sem corpo) encerra a
  sessão.

Um `404` no poll depois de `expires_at` (`SdkEnrollmentNotFound`) significa
o mesmo que a checagem de prazo do próprio cliente: a janela de aprovação
está fechada de qualquer jeito.

## 6. HybridSeal — X25519 + ML-KEM-768

A mesma construção sela a sessão (cofre → SDK) e as DEKs de grupo (app web
→ SDK).

```
eph            = X25519.keygen()
ss1            = X25519(eph.secret, recipient.x25519)                 32 B
(kem_ct, ss2)  = ML-KEM-768.encaps(recipient.mlkem768)                1088 B, 32 B
encapsulation  = eph.public ‖ kem_ct                                  1120 B
key            = HKDF-SHA256(ikm = ss1 ‖ ss2, salt = ∅, info = utf8("imgexam-sdk-hybrid-seal-v1") ‖ encapsulation, L = 32)
nonce          = random(12)
ct             = AES-256-GCM(key, nonce, plaintext, aad = utf8(aad))  (tag anexada, 16 B)
wire           = { "salt": b64url(encapsulation), "nonce": b64url(nonce), "ciphertext": b64url(ct) }
```

`imgexam-sdk-hybrid-seal-v1` é um rótulo congelado — veja
[Rótulos congelados](#rótulos-congelados).

Abertura: separe `salt` em `eph.public[0:32]` e `kem_ct[32:]`, derive
`ss1 = X25519(sk.x25519, eph.public)` e `ss2 = ML-KEM-768.decaps(sk.mlkem768, kem_ct)`,
mesmo HKDF, decifre com AES-GCM. Os dois segredos precisam estar presentes:
o desenho sobrevive a qualquer uma das primitivas cair sozinha — uma
quebra futura do X25519 por computação quântica ainda precisa do ML-KEM-768
quebrado também, e um defeito na implementação mais nova do ML-KEM ainda
deixa o X25519 de pé.

Vetor: `hybrid_seal.json` (contém as chaves secretas do destinatário).

## 7. Envelope de chave e de conteúdo

`EncryptedPayload` (`{salt, nonce, ciphertext}`, tudo b64url) é o único
envelope simétrico do produto.

```
salt     = random(16)
derived  = HKDF-SHA256(ikm = wrapping_key, salt = salt, info = utf8(info), L = 32)
nonce    = random(12)
ct       = AES-256-GCM(derived, nonce, plaintext, aad = ∅)          (tag anexada)
```

`wrapKey` (o plaintext é uma chave) e `encryptContent` (o plaintext é dado)
são os mesmos bytes; só `info` muda. As strings de `info` são versionadas e
nunca compartilhadas entre propósitos — a lista completa e congelada está
em [Rótulos congelados](#rótulos-congelados), logo abaixo.

Vetor: `aes_gcm_envelope.json` (HKDF, wrapKey, encryptContent).

## Rótulos congelados

Todo rótulo de HKDF/AAD abaixo mantém o prefixo histórico `imgexam-` de
propósito. O nome é anterior ao `diagnos`, mas essas strings são constantes
de fio gravadas em todo ciphertext já armazenado — renomear uma tornaria
dados existentes ilegíveis. Nunca reaproveite um rótulo para um significado
novo; uma derivação que muda ganha uma string nova, versionada separadamente
(`-v2`). Código que usa um destes aponta de volta para cá pelo nome — veja
`apps/sdk/src/diagnos/crypto/keys.py`, `hybrid.py` e `hkdf.py`.

| Rótulo | Propósito | Seção |
|---|---|---|
| `imgexam-sdk-hybrid-seal-v1` | `info` do HKDF do selo híbrido (sessão e selagem de chave de grupo) | §6 |
| `imgexam-patient-dek-v1` | embrulha a DEK de um documento de paciente sob a DEK do security group | §7, §8 |
| `imgexam-exam-dek-v1` | embrulha a DEK de um documento de exame | §7, §8 |
| `imgexam-template-dek-v1` | embrulha a DEK de um documento de modelo | §7, §8 |
| `imgexam-patient-record-v1` | cifra o corpo do registro de um paciente | §7, §8 |
| `imgexam-exam-record-v1` | cifra o corpo do registro de um exame | §7, §8 |
| `imgexam-template-record-v1` | cifra o corpo do registro de um modelo | §7, §8 |
| `imgexam-drive-node-key-v1` | deriva a chave de conteúdo de um nó de drive a partir da DEK do grupo (salt = `node_id`) | §9 |
| `imgexam-drive-node-name-v1` | embrulha o nome de arquivo de um nó de drive sob a DEK do grupo | §9 |
| `imgexam-sse-c-v1` | deriva a chave de cliente opcional do SSE-C a partir de uma chave de documento ou de nó | §10 |

## 8. Documentos versionados

> [!WARNING]
> Esta seção descreve a implementação 0.1 do SDK para pacientes, exames e
> modelos, anterior à revisão atual do protocolo do cofre — veja
> [COMPATIBILITY.pt-BR.md](COMPATIBILITY.pt-BR.md). Ela fica aqui como
> registro do que `vault.patients`/`vault.exams` (rotulados **prévia** em
> [`apps/sdk/README.pt-BR.md`](../apps/sdk/README.pt-BR.md)) mandam e esperam hoje, não
> como descrição do que o `vault.diagnos.health` aceita atualmente.

Pacientes, exames e modelos compartilham um modelo: um **índice** que a
API expõe (versões, mais recente, grupos, chaves embrulhadas, `meta` em
claro) e, por versão, um objeto cifrado no R2 que o SDK lê/escreve por URL
assinada. Só o SDK vê texto claro.

Índice (`result.document`):
```json
{ "document_id", "workspace_id", "resource": "patients", "security_groups": ["sg1"],
  "encrypted_keys": { "sg1": <EncryptedKeyPayload> }, "latest_version_id", "versions": [{ "version_id", "size", "created_at", "created_by" }],
  "pending_version_id", "meta": {…}, "created_at", "created_by", "updated_at", "updated_by", "is_archived", "is_deleted" }
```

Chaves:
- `doc_dek` = 32 bytes aleatórios, uma por **documento** (as versões
  reusam). `encrypted_keys[sg]` = `wrapKey(group_dek[sg], doc_dek, "imgexam-<singular>-dek-v1")`
  (veja [Rótulos congelados](#rótulos-congelados) para as três strings
  concretas).
- Corpo do objeto = JSON UTF-8 de `encryptContent(doc_dek, utf8(json(record)), "imgexam-<singular>-record-v1")`,
  isto é, `{"salt":…,"nonce":…,"ciphertext":…}`. `Content-Type: application/json`.

Registros (JSON antes de cifrar):
- `patients` — espelha `@repo/core/schemas/Patient.ts#PatientRecord`:
  `legal_name`, `display_name`, `legal_id?`, `external_id?`, `birth_date?` (data ISO),
  `biological_sex?` (`MALE|FEMALE|INTERSEX|UNDEFINED`), `gender_identity?`, `race_identity?`,
  `internal_notes?: string[]`, `email?`, `phone?`, `custom_attributes?: object`.
- `exams` — `title?`, `description?`, `report?: { format: "html"|"markdown"|"text", content }`, `custom_attributes?: object`.
- `templates` — `title`, `content_html`, `category?`. (só client web.)

`meta` (em claro): patients `{ specialist_ids? }` · exams `{ patient_id, modality?, report_status?, dicom_manifest_status?, … }` · templates `{ category? }`.

Rotas (`{base}` = `/api/external/v1/workspaces/{workspace_id}/{resource}`):
```
GET  {base}?limit=&cursor=&security_group_id=&include_deleted=      → { items: [index…], next_cursor }
POST {base}   { security_groups, encrypted_keys, content_length, meta? }
              → 201 { document, version_id, upload: { url, method: "PUT", headers: { "content-length" }, expires_at } }
PUT  upload.url   (corpo = objeto cifrado; header content-length EXATAMENTE como dado)
POST {base}/{document_id}/versions/{version_id}/commit               → { document }
GET  {base}/{document_id}?version_id=                                 → { document, version, download: { url, method: "GET", expires_at } }
POST {base}/{document_id}/versions   { content_length, meta?, is_archived?, is_deleted? }
              → 201 { document, version_id, upload }   depois PUT, depois commit
```

Não existe atualização parcial nem apagar: mudar é sempre uma versão nova e
inteira; arquivar/apagar são flags do índice gravadas por uma versão nova.
Só quem reservou a versão pode confirmá-la.

## 9. Drives (arquivos)

> [!WARNING]
> Esta seção descreve a implementação 0.1 do SDK para arquivos de drive,
> anterior à revisão atual do protocolo do cofre — veja
> [COMPATIBILITY.pt-BR.md](COMPATIBILITY.pt-BR.md). Ela fica aqui como
> registro do que `vault.drives` (rotulado **prévia** em
> [`apps/sdk/README.pt-BR.md`](../apps/sdk/README.pt-BR.md)) manda e espera hoje, não
> como descrição do que o `vault.diagnos.health` aceita atualmente.

Um drive é um security group. Todo arquivo (DICOM, imagem, vídeo, PDF) é
um **nó** em `{base}` = `/api/external/v1/workspaces/{workspace_id}/drives/{security_group_id}`.

Chaves:
```
node_key       = HKDF-SHA256(ikm = group_dek, salt = utf8(node_id), info = utf8("imgexam-drive-node-key-v1"), L = 32)
encrypted_name = wrapKey(group_dek, utf8(original_file_name), "imgexam-drive-node-name-v1")
```
Derivar a chave de conteúdo da DEK do grupo dispensa chave embrulhada por
nó; a revogação acontece no grupo. O nome é embrulhado com a **DEK do
grupo** (não com a chave do nó) porque viaja no pedido de reserva, antes de
o cofre atribuir um `node_id` — a própria derivação da chave do nó precisa
desse id como salt, que ainda não existe naquele momento.

Corpo (`secretstream.json`): `crypto_secretstream_xchacha20poly1305` do libsodium com `node_key`,
framed como `[header 24 B][len uint32 BE][pedaço cifrado]*`; pedaços de texto
claro de 1 MiB (`1048576`), o último pedaço enviado com `TAG_FINAL` (um
arquivo vazio ainda tem um pedaço final). O leitor remonta os frames pelo
comprimento antes de abrir; as partes de um multipart cortam o stream
framed em offsets arbitrários.

Rotas:
```
POST {base}/uploads   { exam_id?, files: [{ client_ref, size (bytes cifrados), mime_type?, encrypted_name? }] (≤1000) }
   → 201 { nodes: [ { client_ref, node_id, mode: "single", upload } | { client_ref, node_id, mode: "multipart", part_size, part_count } ] }
PUT  upload.url                                   (single: ≤ 64 MiB, content-length exato)
POST {base}/uploads/complete   { node_ids }       → { ready: [node…], missing: [node_id…] }
POST {base}/uploads/{node_id}/multipart           → { upload_id, part_size (32 MiB), part_count }
POST {base}/uploads/{node_id}/multipart/parts   { part_numbers (≤200) } → { parts: [{ part_number, url, expires_at }] }
PUT  part.url  (ETag do header de resposta)  …  POST {base}/uploads/{node_id}/multipart/complete { parts: [{ part_number, etag }] } → { node }
POST {base}/uploads/{node_id}/multipart/abort     → { aborted: true }
GET  {base}/nodes?limit=&cursor=&exam_id=&include_pending=          → { items: [node…], next_cursor }
GET  {base}/nodes/{node_id}                        → { node, download }
```

`size` é o tamanho do corpo **cifrado e framed** — calcule antes de subir
(`24 + Σ(4 + pedaço + 17)`, do header, do prefixo de comprimento e da tag de
17 bytes do secretstream por pedaço). O cofre cobra o workspace por ele.

## 10. SSE-C (opcional)

Os objetos já são cifrados de ponta a ponta. Adicionalmente, PUT/GET
único pode usar o SSE-C do R2 com uma chave que o cofre nunca vê. Desligado
por padrão até o client web adotar (`DIAGNOS_SSE_C=1` liga); nunca usado em
multipart (o cofre cria aquele upload e não pode ficar com a chave).

```
sse_key = HKDF-SHA256(ikm = doc_dek | node_key, salt = ∅, info = utf8("imgexam-sse-c-v1"), L = 32)
x-amz-server-side-encryption-customer-algorithm: AES256
x-amz-server-side-encryption-customer-key:       base64(sse_key)         (base64 padrão, com padding)
x-amz-server-side-encryption-customer-key-MD5:   base64(MD5(sse_key))
```

## 11. Auto-unseal com OpenBao

Opcional. Com `OPENBAO_ADDR` e `OPENBAO_TOKEN` definidas, o SDK salva o
estado desbloqueado depois de um enrollment bem-sucedido e o restaura ao
subir, sem humano. Isso move deliberadamente as DEKs de grupo da RAM para o
armazenamento cifrado do OpenBao: quem conseguir ler aquele path lê o
workspace. Restrinja o token ao path.

KV v2 · `mount = OPENBAO_MOUNT (padrão "secret")`, path `OPENBAO_PATH_PREFIX (padrão "diagnos")/{workspace_id}/{account_id}`:
```json
{ "v": 1, "enrollment_id", "x25519_secret", "mlkem768_secret", "session_id", "sign_key", "enc_key",
  "session_expires_at", "group_keys": { "<sg>": "<32 B b64url>" }, "saved_at" }
```
Restaure só enquanto `session_expires_at − agora > 60 s`; senão, faça um
novo enrollment.

`OPENBAO_TOKEN_FILE` pode nomear um arquivo com o token em vez de
`OPENBAO_TOKEN` (a forma que orquestradores de container preferem). Escrever
este documento é o único momento em que as chaves do SDK de referência saem
da memória travada: são reveladas em buffers zerados logo depois de a
requisição ser montada.

## 12. Erros

| `code` | HTTP | Exceção do SDK |
|---|---|---|
| `ValidationError` | 400 | `ValidationError` |
| `Unauthorized`, `SessionNotFound`, `SignatureInvalid`, `SignatureMissing` | 401 | `AuthenticationError` (sessão sumiu → refaça o enrollment) |
| `SignatureTimestampSkew` | 401 | ressincroniza o relógio, tenta uma vez, depois `AuthenticationError` |
| `QuotaExceeded`, `BudgetNotProvisioned` | 402 | `QuotaError` |
| `ServiceAccountRevoked`, `DocumentAccessDenied`, `InsufficientPermission`, `NotAWorkspaceMember` | 403 | `DiagnosPermissionError` |
| `DocumentNotFound`, `DocumentVersionNotFound`, `DriveNodeNotFound`, `SdkEnrollmentNotFound`, `NotFound` | 404 | `NotFoundError` |
| `DocumentVersionPending`, `DocumentVersionNotPending`, `ReplayDetected`, `DriveNodeNotPending` | 409 | `ConflictError` (`ReplayDetected` é retentado uma vez, com nonce novo) |
| `RateLimitExceeded` | 429 | `RateLimitError` (respeita `Retry-After` se vier; senão backoff com jitter, até 3 tentativas) |
| `RequestBodyTooLarge` | 413 | `ValidationError` |
| 5xx / `InternalServerError` | 5xx | `VaultError` (carrega `trace_id`; uma retentativa depois de um backoff fixo) |

Uma resposta que não é JSON válido (uma página de erro de proxy, um corpo
truncado) não carrega `code` nenhum; o SDK lança `VaultError` com o código
sintético `InvalidResponse` em vez de deixar vazar um erro de parse cru.
`SessionExpiredError` é um erro puramente local — o SDK não tem sessão viva
para assinar com — e nunca vem de uma resposta do cofre.

## 13. Limites

Corpo de API 1 MiB · versão de documento ≤ 64 MiB · lote ≤ 1000 arquivos · arquivo único ≤ 64 MiB · parte de multipart 32 MiB, ≤ 200 URLs de parte por chamada · página de lista ≤ 200.
