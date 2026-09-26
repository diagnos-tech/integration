# PROTOCOL — o contrato entre o SDK e o cofre

[English](PROTOCOL.md) · **Português (Brasil)**

Normativo. Todo formato abaixo está travado por `apps/sdk/tests/vectors/*.json`,
gerados a partir da implementação de referência do cofre. Quando este
documento e um vetor discordarem, o vetor vence e este documento tem um bug.

O documento inteiro corresponde a `vault.diagnos.health` e ao app web como
eles rodam hoje. Questões ainda em aberto do lado do cofre — nenhuma muda um
byte do que o SDK manda — ficam em [COMPATIBILITY.pt-BR.md](COMPATIBILITY.pt-BR.md).

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

`EncryptedPayload` (`{salt, nonce, ciphertext}`, tudo b64url) é o envelope
simétrico de chaves e de payloads JSON pequenos.

```
salt     = random(16)
derived  = HKDF-SHA256(ikm = wrapping_key, salt = salt, info = utf8(info), L = 32)
nonce    = random(12)
ct       = AES-256-GCM(derived, nonce, plaintext, aad = ∅)          (tag no fim)
```

`wrapKey` (o texto claro é uma chave) e `encryptContent` (o texto claro é
dado) são os mesmos bytes; só o `info` muda. As strings de `info` são
versionadas e nunca compartilhadas entre propósitos — a lista completa e
congelada está em [Rótulos congelados](#rótulos-congelados) abaixo.

Objetos guardados (uma versão de documento, uma cabeça de rascunho) nunca
usam uma chave de longa duração direto. Cada objeto ganha a própria **chave
de conteúdo**, derivada da DEK do documento e do `security_context` que o
cofre devolve junto de toda URL assinada de upload/download — opaco para o
cliente, amarrado pelo cofre ao endereço real do objeto:

```
content_key = HKDF-SHA256(ikm = dek, salt = utf8(key_id), info = utf8(security_context.value), L = 32)
key_id      = version_id                           (uma versão confirmada)
            = "draft"  |  "draft:<fluxo>"          (a cabeça de rascunho; "draft:<fluxo>" em recurso de vários fluxos)
```

O corpo do objeto é binário cru — sem JSON, sem base64 — selado com a mesma
primitiva do envelope acima:

```
body           = salt(16) ‖ nonce(12) ‖ AES-256-GCM(HKDF-SHA256(content_key, salt, utf8(info)), nonce, plaintext)
info           = "imgexam-document-version-v1"  (uma versão)  |  "imgexam-document-draft-v1"  (um rascunho)
content_length = len(plaintext) + 44            (declarado antes de selar; o PUT assinado o trava)
```

Vetores: `aes_gcm_envelope.json` (HKDF, wrapKey, encryptContent);
`document_content.json` (a DEK de um documento, a chave de conteúdo, uma
versão selada, um rascunho selado e os dois resumos `encrypted_index` —
selados pelo próprio código do app web).

## Rótulos congelados

Todo rótulo de HKDF/AAD abaixo mantém o prefixo histórico `imgexam-` de
propósito. O nome é anterior ao `diagnos`, mas essas strings são constantes
de fio embutidas em todo ciphertext já gravado — renomear uma tornaria dado
existente ilegível. Nunca reaproveite um rótulo para um significado novo;
uma derivação alterada ganha uma string nova, versionada à parte (`-v2`).
Código que usa um destes aponta de volta para cá pelo nome — ver
`apps/sdk/src/diagnos/crypto/keys.py`, `content.py`, `hybrid.py` e `hkdf.py`.

| Rótulo | Propósito | Seção |
|---|---|---|
| `imgexam-sdk-hybrid-seal-v1` | `info` do HKDF do selo híbrido (selagem de sessão e de chave de grupo) | §6 |
| `imgexam-patient-dek-v1` | embrulha a DEK de **todo** documento (pacientes, exames, modelos) sob a chave do security group — o app web usa este único rótulo para os três | §7, §8 |
| `imgexam-patient-index-v1` | sela o `encrypted_index` de um paciente sob a DEK | §8 |
| `imgexam-exam-index-v1` | sela o `encrypted_index` de um exame | §8 |
| `imgexam-template-index-v1` | sela o `encrypted_index` de um modelo de laudo | §8 |
| `imgexam-document-version-v1` | sela o corpo de uma versão confirmada sob a chave de conteúdo dela | §7, §8 |
| `imgexam-document-draft-v1` | sela o corpo de uma cabeça de rascunho sob a chave de conteúdo dela | §7, §8 |
| `imgexam-node-dek-v1` | embrulha a DEK do próprio nó sob a chave do security group dele | §9 |
| `imgexam-node-name-v1` | sela o nome de um nó sob a DEK dele | §9 |
| `\|sse-c-v1` | sufixo somado a `security_context.value` para derivar a chave de SSE-C de um nó | §10 |

## 8. Documentos versionados

Pacientes, exames e modelos de laudo compartilham um modelo: um **índice**
no Firestore que a API expõe (fluxos de versões, a DEK embrulhada, um resumo
selado, `meta` em claro) e, por versão, um objeto selado no R2 que o SDK lê
e grava por URLs assinadas. Só clientes veem texto claro. A API externa
serve pacientes e exames; modelos existem só no app web.

**Fluxos.** Um documento tem um ou mais fluxos independentes de versões.
Exames (e modelos) têm um, `data`. Pacientes têm dois: `data` (o registro
estruturado) e `file` (o documento rico do editor web, Lexical + Yjs, não
exposto pelo SDK). Isso decide a forma das rotas de versão: um recurso de
vários fluxos leva `/streams/{fluxo}`, um de fluxo único não.

Índice (`result.document`, a mesma forma em toda resposta):
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

Um documento pertence a **exatamente um** security group: compartilhar um
paciente com outra equipe é copiá-lo, nunca compartilhar a chave.

Chaves:
- `dek` = 32 bytes aleatórios, um por **documento**, compartilhado por todo
  fluxo e versão. `encrypted_keys[security_group_id]` =
  `wrapKey(group_key, dek, "imgexam-patient-dek-v1")` — para todo recurso.
- O corpo de cada versão é selado sob a própria chave de conteúdo (§7), com
  `key_id = version_id`; uma cabeça de rascunho com `key_id = "draft"`
  (fluxo único) ou `"draft:<fluxo>"` (vários fluxos).
- `encrypted_index` = `encryptContent(dek, utf8(json(resumo)), "imgexam-<recurso>-index-v1")`,
  regravado a cada versão, para listas abrirem sem baixar nenhuma.

Registros (JSON antes de selar; campos ausentes ficam de fora):
- `patients` (fluxo `data`) — `legal_name`, `display_name`,
  `identifiers?: [{ name, value }]` (cada `value` é `secret:v1:…`, selado
  pela rota de dado sensível do cofre; abrir um é auditado),
  `external_id?`, `birth_date?`, `biological_sex?`
  (`MALE|FEMALE|INTERSEX|UNDEFINED`), `gender_identity?`, `race_identity?`,
  `email?`, `phone?`, `address?: { postal_code?, street?, number?,
  complement?, district?, city?, state?, country? }`, `internal_notes?:
  string[]`, `custom_attributes?: object`.
- `exams` — `title?`, `modality?`, `exam_date?`, `report_lexical?` (o estado
  do editor, a fonte da verdade), `report_html?` (derivado dele),
  `custom_attributes?: object`.

Resumos (o texto claro de `encrypted_index`): pacientes
`{ display_name, legal_name, external_id?, birth_date?, tags: string[] }` —
nunca documentos de identidade; exames `{ title?, modality?, exam_date? }`.

Datas são instantes ISO 8601 em UTC (`Date.toISOString()`), truncados na
precisão de anonimização do workspace (`month|day|hour|minute|second`)
antes de selar.

`meta` (em claro, o que o próprio cofre lê): pacientes `{ specialist_ids? }` ·
exames `{ patient_id, modality?, report_status?, published_at?,
published_by? }` — o app web grava só `patient_id`; todo dado clínico fica
selado.

Rotas (`{base}` = `/api/external/v1/workspaces/{workspace_id}/{patients|exams}`,
`{s}` = `/streams/{fluxo}` em pacientes, vazio em exames):
```
GET  {base}?limit=&cursor=&security_group_id=&include_deleted=true    → { items: [índice…], next_cursor }
POST {base}   { security_group_id, encrypted_keys, content_length, encrypted_index, stream: "data", meta? }
              → 201 { document, stream, version_id, security_context: { value, kid },
                      upload: { url, method: "PUT", headers: { "content-length", … }, client_headers, expires_at } }
PUT  upload.url                                            (corpo = objeto selado, content-length exatamente como assinado)
POST {base}/{id}{s}/versions/{version_id}/commit           → { document }        (idempotente ao reenviar)
GET  {base}/{id}?stream=&version_id=                       → { document, stream, version, security_context, download }
POST {base}/{id}{s}/versions   { content_length, encrypted_index?, meta?, expected_latest_version_id? }
              → 201 { staged: true, document, stream, version_id, security_context, upload }   depois PUT, depois commit
POST {base}/{id}{s}/versions   { is_archived?, is_deleted? }                    (sem content_length: só patch)
              → 200 { staged: false, document }
GET  {base}/{id}{s}/draft                                  → { download, security_context, draft_rev, draft_size, updated_at } | null
PUT  {base}/{id}{s}/draft      { content_length, draft_rev? } → { upload, security_context, draft_rev }   (o autosave do editor web)
```

Regras:
- Uma mudança é sempre uma versão nova e completa; não existe atualização
  parcial. Arquivar e apagar são flags ligadas por uma reserva só de patch —
  sem versão nova, sem upload — e apagar nunca é um apagar de verdade.
- Uma versão pendente por fluxo: uma segunda reserva responde
  `409 DocumentVersionPending` até a primeira ser confirmada ou expirar
  (retente por pouco tempo). `expected_latest_version_id` responde
  `409 DocumentVersionMismatch` quando outra versão foi confirmada depois.
  Um commit antes de o objeto ser enviado responde `400 DocumentObjectNotFound`.
- Leitura: a cabeça de rascunho vence quando existe e o `updated_at` dela é
  posterior ao `created_at` da versão corrente; senão a versão corrente
  vence (um commit não apaga o rascunho, só o supera).
- O cofre lista headers de SSE-C junto das URLs de documento, mas o app web
  não usa SSE-C em documento — nem no `PUT` nem no `GET` — então o SDK manda
  só o `content-length` assinado e lê com um `GET` simples. Uma segunda
  camada que só um lado mandasse tornaria o objeto ilegível para o outro.

## 9. Arquivos e pastas (nós)

Todo arquivo (DICOM, imagem, vídeo, PDF) e toda pasta de um workspace é um
**nó** em `{base}` = `/api/external/v1/workspaces/{workspace_id}/nodes`.
Um nó pertence a um security group; ler um precisa só do id — o cofre
autoriza contra o grupo que o próprio nó declara.

Chaves, como o pipeline de upload do app web (`@repo/magic-files`) as monta:
```
node_dek       = random(32)                                          (uma por nó, arquivo ou pasta)
encrypted_keys = { <security_group_id>: wrapKey(group_key, node_dek, "imgexam-node-dek-v1") }
encrypted_name = encryptContent(node_dek, utf8(nome), "imgexam-node-name-v1")
content_key    = HKDF-SHA256(ikm = node_dek, salt = utf8(node_id), info = utf8(security_context.value), L = 32)
```
A chave de conteúdo é a derivação dos documentos (§7) com
`key_id = node_id` — o cofre também devolve esse id como `version_id`, já
que nós não são versionados. O `security_context` volta na reserva, antes
de o primeiro byte ser selado, e de novo junto de toda URL de download. O
nome é o que quem subiu escolheu: o app web sela um caminho relativo
(`exames/2024/IM-0001.dcm`), então quem lê nunca deve usá-lo como caminho
local sem tratar.

Corpo (`secretstream.json`, `node_content.json`): libsodium
`crypto_secretstream_xchacha20poly1305` sob `content_key`, enquadrado como
`header(24) ‖ (len_u32_be ‖ frame)*`. O texto claro vai em pedaços de
1 MiB (`1048576`), todo pedaço cheio como mensagem comum; o resto —
**vazio quando o tamanho é múltiplo exato** — sempre vai por último, como um
frame `TAG_FINAL` próprio. Então, para `n` bytes de texto claro:

```
size = 24 + (⌊n / 1048576⌋ + 1) × (4 + 17) + n
```

`size` é declarado na reserva e o cofre assina o `PUT` para exatamente essa
quantidade de bytes, então ele é calculado antes de cifrar; o cofre também
cobra o workspace por ele. Um upload multipart corta o fluxo de bytes
enquadrado em offsets fixos (`part_size`), nunca nas bordas dos frames.

Rotas:
```
POST {base}/uploads   { security_group_id, exam_id?, parent_id?, files: [entrada] (≤ 100) }
     entrada = { client_ref (≤ 64 caracteres), encrypted_name, encrypted_keys, size, mime_type? }   um arquivo
             | { kind: "folder", client_ref, encrypted_name, encrypted_keys }                       uma pasta
  → 201 { items: [{ client_ref, node_id, version_id, security_context, kind,
                    mode?: "single" | "multipart", upload?, part_size?, part_count?, upload_id? }] }
PUT  upload.url   com upload.headers + SSE-C (§10)                            single: size ≤ 64 MiB
POST {base}/uploads/complete             { node_ids (≤ 200) } → { ready: [nó…], missing: [node_id…] }
POST {base}/{node_id}/multipart                               → { upload_id, part_size (32 MiB), part_count }
POST {base}/{node_id}/multipart/parts    { part_numbers (≤ 200) } → { parts: [{ part_number, url, expires_at }] }
PUT  part.url     com SSE-C (§10); o ETag volta como header da resposta
POST {base}/{node_id}/multipart/complete { parts: [{ part_number, etag }] } → { node }
POST {base}/{node_id}/multipart/abort                         → { aborted: true }
GET  {base}?security_group_id=&exam_id=&parent_id=&include_pending=&limit=&cursor=   → { items: [nó…], next_cursor }
GET  {base}/{node_id}                                         → { node, security_context, download }
```

- **Reserva idempotente.** O cofre deduplica uma reserva por
  `(workspace, client_ref)`: reenviar a mesma ref (mesmo chamador, mesmo
  grupo, ainda pendente) devolve o mesmo nó e cobra uma vez só. Um client
  sorteia uma ref por arquivo e a reusa quando tenta de novo.
- **Pastas** ficam prontas na hora — não há conteúdo a subir. `parent_id`
  precisa ser uma pasta pronta do mesmo grupo.
- **Arquivos pequenos** (≤ 64 MiB) sobem cada um num `PUT` assinado e são
  confirmados juntos; `missing` nomeia os nós cujo objeto nunca chegou.
- **Arquivos grandes** sobem por partes. A reserva em geral já abre o
  upload multipart (`upload_id`); só quando não abriu o client chama
  `{node_id}/multipart`. Um upload abortado deixa o nó `failed`; uma
  reserva abandonada expira depois de 6 h.
- **Leituras.** `GET {base}/{node_id}` responde `404` para uma pasta ou um
  upload inacabado — não há o que baixar. Uma listagem mostra só nós
  prontos, a menos que `include_pending=true`.

## 10. SSE-C

A criptografia do lado do servidor do R2 com chave do cliente é uma segunda
camada em cima da cifragem ponta a ponta da §9; o cofre nunca vê a chave. O
app web a deriva como irmã da chave de conteúdo e a manda no `PUT` único, em
toda parte de multipart e no `GET` — um objeto gravado com SSE-C só pode ser
lido com a mesma chave:

```
sse_c_key = HKDF-SHA256(ikm = node_dek, salt = utf8(node_id), info = utf8(security_context.value ‖ "|sse-c-v1"), L = 32)
x-amz-server-side-encryption-customer-algorithm: AES256
x-amz-server-side-encryption-customer-key:       base64(sse_c_key)            (base64 padrão, com padding)
x-amz-server-side-encryption-customer-key-md5:   base64(MD5(sse_c_key))
```

`upload.headers` e `download.headers` levam os valores que o cofre fixa
(`content-length`, `content-type`, o algoritmo) e precisam ser mandados como
vieram; `client_headers` nomeia os dois cujos valores só o client conhece.
Documentos versionados (§8) não usam SSE-C. As questões ainda em aberto do
lado do cofre sobre esta camada estão em
[COMPATIBILITY.pt-BR.md](COMPATIBILITY.pt-BR.md).

**Hosts de armazenamento.** Uma URL pré-assinada — de documento ou de
arquivo — só é seguida quando é HTTPS num host permitido ou num subdomínio
dele: por padrão o domínio de conteúdo de usuário `diagnosusercontent.com` e
o `r2.cloudflarestorage.com` do R2, contra o qual o cofre assina hoje.
`DIAGNOS_STORAGE_HOSTS` (separado por vírgula) substitui a lista. Qualquer
outra coisa é recusada antes de um byte sair (`ProtocolError`): ciphertext e
chaves de SSE-C só vão para onde o deploy escolheu.

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
| `ValidationError`, `DocumentTooLarge`, `DocumentObjectNotFound`, `DriveBatchTooLarge`, `DriveDuplicateClientRef`, `DriveFileTooLarge`, `DriveInvalidParent`, `DriveObjectNotFound` | 400 | `ValidationError` |
| `Unauthorized`, `SessionNotFound`, `SignatureInvalid`, `SignatureMissing` | 401 | `AuthenticationError` (sessão sumiu → refaça o enrollment) |
| `SignatureTimestampSkew` | 401 | ressincroniza o relógio, tenta uma vez, depois `AuthenticationError` |
| `QuotaExceeded`, `BudgetNotProvisioned` | 402 | `QuotaError` |
| `ServiceAccountRevoked`, `DocumentAccessDenied`, `InsufficientPermission`, `NotAWorkspaceMember`, `DriveUploadNotOwned` | 403 | `DiagnosPermissionError` |
| `DocumentNotFound`, `DocumentVersionNotFound`, `DriveNodeNotFound`, `SdkEnrollmentNotFound`, `NotFound` | 404 | `NotFoundError` |
| `DocumentVersionPending`, `DocumentVersionNotPending`, `DocumentVersionMismatch`, `DocumentDraftMismatch`, `ReplayDetected`, `DriveNodeNotPending`, `UploadIncomplete` | 409 | `ConflictError` (`ReplayDetected` é retentado uma vez, com nonce novo; `DocumentVersionPending` numa reserva é retentado depois de 1,5 s e 3 s) |
| `RateLimitExceeded` | 429 | `RateLimitError` (respeita `Retry-After` se vier; senão backoff com jitter, até 3 tentativas) |
| `RequestBodyTooLarge` | 413 | `ValidationError` |
| 5xx / `InternalServerError`, `MultipartUploadFailed` | 5xx | `VaultError` (carrega `trace_id`; uma retentativa depois de um backoff fixo) |

Uma resposta que não é JSON válido (uma página de erro de proxy, um corpo
truncado) não carrega `code` nenhum; o SDK lança `VaultError` com o código
sintético `InvalidResponse` em vez de deixar vazar um erro de parse cru.
`SessionExpiredError` é um erro puramente local — o SDK não tem sessão viva
para assinar com — e nunca vem de uma resposta do cofre. `ProtocolError` é
lançado quando uma resposta bem formada quebra o protocolo (um tamanho
assinado que não é o do corpo selado, uma reserva de versão respondida como
só-patch, uma parte no armazenamento sem ETag). `UploadIncomplete` é lançado
pelo SDK, não pelo cofre: `uploads/complete` listou um nó em `missing`,
então o `PUT` dele nunca chegou — suba aquele arquivo de novo. Um commit que
falha na rede ou com 5xx é reenviado com backoff (0,5 s, 1 s): commits são
idempotentes. Um upload multipart que falha no meio é abortado antes de o
erro ser lançado.

## 13. Limites

Corpo de API 1 MiB · versão de documento ≤ 64 MiB · arquivo ≤ 50 GiB · ≤ 100 arquivos por reserva · ≤ 200 ids de nó por confirmação · `PUT` único ≤ 64 MiB · parte de multipart 32 MiB, ≤ 200 URLs de parte por chamada · página de lista ≤ 200 · um upload pendente expira depois de 6 h, as URLs assinadas dele depois de 1 h.
