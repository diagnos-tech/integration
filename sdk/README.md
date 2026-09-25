# diagnos

🇺🇸 The official zero-knowledge Python SDK for the diagnos vault
(`vault.diagnos.health`). Patients, exams and drive files are encrypted in this
process, in RAM, before a single byte reaches the network — the vault only
ever sees ciphertext, signed requests and presigned URLs. This package is the
one place that complexity lives, so your code can read like this:

🇧🇷 O SDK Python oficial, zero-knowledge, do cofre diagnos
(`vault.diagnos.health`). Pacientes, exames e arquivos de drive são cifrados
neste processo, na RAM, antes de um único byte chegar à rede — o cofre só vê
ciphertext, requisições assinadas e URLs pré-assinadas. Este pacote é o único
lugar onde essa complexidade mora, para o seu código poder ler assim:

```python
from diagnos import Diagnos

with Diagnos() as vault:
    for index in vault.patients.list():
        patient = vault.patients.get(index.document_id)
        print(patient.record.legal_name)
```

## Install · Instalação

```sh
pip install diagnos
export DIAGNOS_API_TOKEN="apikey-…"   # 🇺🇸 issued by a workspace admin · 🇧🇷 emitido por um admin do workspace
```

🇺🇸 `DIAGNOS_API_TOKEN` identifies *this* service account and its workspace;
it does not, by itself, unlock anything — see below.
🇧🇷 `DIAGNOS_API_TOKEN` identifica *esta* service account e o workspace dela;
sozinho, ele não desbloqueia nada — veja abaixo.

## 30 seconds to your first `list()` · 30 segundos até o primeiro `list()`

```python
from diagnos import Diagnos

vault = Diagnos()  # 🇺🇸 reads DIAGNOS_API_TOKEN · 🇧🇷 lê DIAGNOS_API_TOKEN
vault.unlock()  # 🇺🇸 prints a link + a 6-digit code, waits for approval
# 🇧🇷 imprime link + código de 6 dígitos, espera aprovação

for index in vault.patients.list():
    print(index.document_id, index.updated_at)
```

🇺🇸 You do not even have to call `unlock()` yourself: the first time you touch
`vault.patients`, `vault.exams` or `vault.drives`, the SDK unlocks lazily.
`unlock()` (and the lazy path) are idempotent — call them as many times as
you like, from as many call sites as you like.
🇧🇷 Você nem precisa chamar `unlock()`: na primeira vez que você toca
`vault.patients`, `vault.exams` ou `vault.drives`, o SDK desbloqueia sozinho.
`unlock()` (e o caminho preguiçoso) são idempotentes — chame quantas vezes
quiser, de quantos lugares quiser.

## Enrollment: the link and the code · Enrollment: o link e o código

🇺🇸 The first time an SDK process runs (and every time after, unless
auto-unseal is configured — see below), it has to *enroll*:

1. It generates a hybrid key pair (X25519 + ML-KEM-768) in RAM and registers
   it with the vault, together with a description of where it is running
   (OS, container, hostname, user) — so the person approving can recognize
   the machine asking.
2. It prints a link and a 6-digit code to `stderr`. A workspace admin opens
   the link in the diagnos web app, reads the runtime description, types the
   code, and picks which security groups this SDK process may read.
3. The web app seals the DEKs of those groups **to the SDK's public keys**;
   the vault seals the session keys the same way. The SDK polls, opens both
   with the private keys that never left the process, and is unlocked.

Until a human approves, `unlock()` blocks. There is no way around that step —
it is the whole security model, not friction to route around.

🇧🇷 Na primeira vez que um processo do SDK roda (e em toda vez depois, a
menos que o auto-unseal esteja configurado — veja abaixo), ele precisa fazer
*enrollment*:

1. Gera um par de chaves híbrido (X25519 + ML-KEM-768) na RAM e o registra no
   cofre, com uma descrição de onde está rodando (SO, container, hostname,
   usuário) — para quem aprova reconhecer a máquina que está pedindo.
2. Imprime um link e um código de 6 dígitos em `stderr`. Um admin do
   workspace abre o link no app web, lê a descrição, digita o código, e
   escolhe quais security groups este processo do SDK pode ler.
3. O app web sela as DEKs desses grupos **para as chaves públicas do SDK**; o
   cofre sela as chaves de sessão do mesmo jeito. O SDK faz poll, abre as
   duas com as chaves privadas que nunca saíram do processo, e está
   desbloqueado.

Até uma pessoa aprovar, `unlock()` bloqueia. Não existe atalho para esse
passo — é o modelo de segurança inteiro, não um atrito para contornar.

```python
from diagnos import Diagnos, EnrollmentPrompt


def show_prompt(prompt: EnrollmentPrompt) -> None:
    print(f"Open {prompt.approval_url} and type {prompt.code}")


vault = Diagnos(
    on_prompt=show_prompt
)  # 🇺🇸 default prompt already prints to stderr · 🇧🇷 o prompt padrão já imprime em stderr
vault.unlock()
```

## Auto-unseal with OpenBao · Auto-unseal com OpenBao

🇺🇸 A human approval on every restart is fine for a laptop script; it is not
fine for a Kubernetes pod or a cron job. Set `OPENBAO_ADDR`/`OPENBAO_TOKEN`
and the SDK saves its unlocked state (session keys, group DEKs, the SDK's own
key pair) to OpenBao's encrypted KV store right after a successful
enrollment, and restores from there on the next start — no human needed,
until the saved session itself expires.

**The tradeoff, stated plainly**: this moves your group DEKs from "only ever
in this process's RAM" to "also in OpenBao's storage, at
`<OPENBAO_PATH_PREFIX>/<workspace_id>/<account_id>`". Whoever can read that
one path can decrypt exactly what this SDK process can. Scope the OpenBao
token to that path and nothing wider — that is what keeps this an
intentional trade, not a silent leak.

🇧🇷 Uma aprovação humana a cada reinício é aceitável num script de notebook;
não é aceitável num pod Kubernetes ou num cron job. Configure
`OPENBAO_ADDR`/`OPENBAO_TOKEN` e o SDK salva o estado desbloqueado (chaves de
sessão, DEKs de grupo, o par de chaves do próprio SDK) no KV cifrado do
OpenBao logo depois de um enrollment bem-sucedido, e restaura de lá na
próxima subida — sem humano, até a sessão salva em si expirar.

**O tradeoff, sem rodeios**: isso move suas DEKs de grupo de "só na RAM deste
processo" para "também no armazenamento do OpenBao, em
`<OPENBAO_PATH_PREFIX>/<workspace_id>/<account_id>`". Quem conseguir ler
aquele único path decifra exatamente o que este processo do SDK decifra.
Restrinja o token do OpenBao a esse path e nada mais amplo — é isso que
mantém isto uma troca intencional, não um vazamento silencioso.

```sh
export OPENBAO_ADDR="https://openbao.internal:8200"
export OPENBAO_TOKEN="…"           # 🇺🇸 scoped to this one path · 🇧🇷 restrito a este único path
```

```python
vault = Diagnos()  # 🇺🇸 auto_unseal defaults to True once OPENBAO_ADDR is set
# 🇧🇷 auto_unseal é True por padrão assim que OPENBAO_ADDR está definido
vault.unlock()  # 🇺🇸 restores silently if a valid session was saved; else enrolls
# 🇧🇷 restaura em silêncio se havia sessão válida salva; senão, faz enrollment
```

## Where secrets live · Onde os segredos moram

🇺🇸 Every key this SDK holds — session keys, the DEK of each security
group, the DEK of each document, the SDK's own X25519 + ML-KEM-768 identity —
lives in a small Rust extension shipped inside the wheel, `diagnos._secure`
(`sdk/native/`). A key there is a `SecretBox`: bytes in memory that is locked
in RAM (`mlock`, never swapped), excluded from core dumps, fenced by guard
pages, zeroed in a `fork()` child and zeroed the instant the box is dropped.
It never comes back to Python as `bytes` — signing a request, opening a
seed, unwrapping a document key, encrypting a file all happen inside the
extension. Unlocking a session also hardens the process: core dumps off,
`ptrace` attach denied. None of this changes how you use the SDK; it changes
what an attacker with a swap file, a core dump or a debugger can find.

🇧🇷 Toda chave que este SDK segura — chaves de sessão, a DEK de cada
security group, a DEK de cada documento, a própria identidade X25519 +
ML-KEM-768 do SDK — vive numa extensão Rust pequena embarcada no wheel,
`diagnos._secure` (`sdk/native/`). Uma chave lá é um `SecretBox`: bytes em
memória travada na RAM (`mlock`, nunca vai ao swap), excluída de core dumps,
cercada por guard pages, zerada num filho de `fork()` e zerada no instante em
que a caixa é descartada. Ela nunca volta ao Python como `bytes` — assinar
uma requisição, abrir uma semente, desembrulhar a chave de um documento,
cifrar um arquivo acontecem dentro da extensão. Desbloquear uma sessão também
endurece o processo: core dumps desligados, attach de `ptrace` negado. Nada
disso muda como você usa o SDK; muda o que um atacante com um arquivo de
swap, um core dump ou um debugger consegue encontrar.

🇺🇸 Locking memory counts against `ulimit -l` (often 64 KiB in containers).
When the kernel refuses, the SDK keeps every other protection, logs it and
emits one `MemoryLockWarning`; set `DIAGNOS_MEMORY_LOCK=require` to refuse to
run that way instead. To let a non-root container lock memory, grant
`CAP_IPC_LOCK` (see `api/deploy/README.md`). `sdk/native/README.md` states
exactly what is and is not guaranteed.

🇧🇷 Travar memória conta contra `ulimit -l` (muitas vezes 64 KiB em
containers). Quando o kernel recusa, o SDK mantém toda outra proteção,
registra em log e emite um `MemoryLockWarning`; defina
`DIAGNOS_MEMORY_LOCK=require` para se recusar a rodar assim. Para um
container sem root travar memória, conceda `CAP_IPC_LOCK` (veja
`api/deploy/README.md`). `sdk/native/README.md` diz exatamente o que é e o
que não é garantido.

## Patients · Pacientes

```python
from diagnos import PatientRecord

patient = vault.patients.create(
    {
        "legal_name": "Jane Doe",
        "display_name": "Jane",
    },  # 🇺🇸 a dict is validated for you · 🇧🇷 um dict é validado para você
    security_group="sg_oncology",
    specialist_ids=["specialist_123"],
)

patient = vault.patients.get(patient.id)
patient = vault.patients.update(patient.id, PatientRecord(legal_name="Jane R. Doe", display_name="Jane"))

vault.patients.archive(patient.id)
vault.patients.unarchive(patient.id)
vault.patients.delete(
    patient.id
)  # 🇺🇸 flags the index; the encrypted history stays · 🇧🇷 marca o índice; o histórico cifrado permanece

for index in vault.patients.iter_all(security_group="sg_oncology"):
    ...
```

## Exams · Exames

```python
from diagnos import ExamRecord

exam = vault.exams.create(
    ExamRecord(title="Chest CT", report={"format": "text", "content": "unremarkable"}),
    patient_id=patient.id,  # 🇺🇸 required, clear in the index — the vault routes by it · 🇧🇷 obrigatório, em claro no índice — o cofre roteia por ele
    security_group="sg_oncology",
    modality="CT",
)

exam = vault.exams.get(exam.id)
print(exam.patient_id, exam.record.report.content)
```

## Drives (files) · Drives (arquivos)

🇺🇸 A drive is a security group; every file inside it (DICOM, image, video,
PDF, report) is a *node*. Small files go straight up in one `PUT`; large
ones are split into encrypted parts automatically — you never choose which.
🇧🇷 Um drive é um security group; todo arquivo dentro dele (DICOM, imagem,
vídeo, PDF, laudo) é um *nó*. Arquivo pequeno sobe direto num `PUT`; grande é
partido em pedaços cifrados automaticamente — você nunca escolhe qual.

```python
from diagnos.resources import UploadSource

drive = vault.drives.drive("sg_oncology")

node = drive.upload("chest_ct.dcm", name="chest_ct.dcm", mime_type="application/dicom", exam_id=exam.id)
node = drive.upload(b"raw bytes work too", name="note.txt")

nodes = drive.upload_many(
    [UploadSource("slide_1.jpg", name="slide_1.jpg"), UploadSource("slide_2.jpg", name="slide_2.jpg")],
    exam_id=exam.id,
)  # 🇺🇸 one reservation call for the whole batch · 🇧🇷 uma única chamada de reserva para o lote inteiro

data = drive.download(node.node_id)  # 🇺🇸 bytes in RAM · 🇧🇷 bytes na RAM
drive.download(node.node_id, "downloaded_ct.dcm")  # 🇺🇸 straight to a file · 🇧🇷 direto para um arquivo

for node in drive.list(exam_id=exam.id):
    print(drive.name_of(node), node.size)
```

🇺🇸 `upload`/`upload_many` decide single vs. multipart for you, from the
file's size (`docs/PROTOCOL.md §9`) — nothing to choose.
🇧🇷 `upload`/`upload_many` decidem single ou multipart por você, a partir do
tamanho do arquivo (`docs/PROTOCOL.md §9`) — nada para escolher.

## Errors · Erros

🇺🇸 Every exception is in `diagnos` — catch by class, never by message
(`docs/PROTOCOL.md §12`):

🇧🇷 Toda exceção está em `diagnos` — capture por classe, nunca por mensagem
(`docs/PROTOCOL.md §12`):

| Class · Classe | When · Quando |
|---|---|
| `ValidationError` | 🇺🇸 the request itself is wrong · 🇧🇷 a requisição está errada |
| `AuthenticationError` | 🇺🇸 token/session/signature rejected — usually re-enroll · 🇧🇷 token/sessão/assinatura recusados — em geral, refaça o enrollment |
| `QuotaError` | 🇺🇸 the workspace has no credit for this · 🇧🇷 o workspace não tem crédito para isto |
| `DiagnosPermissionError` | 🇺🇸 this service account may not do this here · 🇧🇷 esta service account não pode fazer isto aqui |
| `NotFoundError` | 🇺🇸 404 · 🇧🇷 404 |
| `ConflictError` | 🇺🇸 a pending version or a replay — the SDK already retried what is safe to retry · 🇧🇷 uma versão pendente ou um replay — o SDK já retentou o que é seguro retentar |
| `RateLimitError` | 🇺🇸 raised only after the SDK's own backoff gave up · 🇧🇷 lançado só depois do backoff do próprio SDK desistir |
| `diagnos.session.keyring.GroupKeyUnavailable` | 🇺🇸 this enrollment was never handed the DEK of a group the document needs · 🇧🇷 este enrollment nunca recebeu a DEK de um grupo que o documento precisa |
| `EnrollmentDeniedError` / `EnrollmentExpiredError` | 🇺🇸 nobody approved, or approved too late · 🇧🇷 ninguém aprovou, ou aprovou tarde demais |
| `VaultError` | 🇺🇸 base class; carries `code`, `status`, `trace_id` for a support ticket · 🇧🇷 classe base; carrega `code`, `status`, `trace_id` para um chamado de suporte |

## Configuration · Configuração

| Env var | Default · Padrão | 🇺🇸 · 🇧🇷 |
|---|---|---|
| `DIAGNOS_API_TOKEN` | — (required · obrigatório) | The `apikey-<jwt>` a workspace admin issued. · O `apikey-<jwt>` emitido por um admin do workspace. |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | Where the vault lives. · Onde o cofre mora. |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | Per-request HTTP timeout. · Timeout HTTP por requisição. |
| `DIAGNOS_SSE_C` | off | Adds R2 SSE-C on top of end-to-end encryption for single PUT/GET (`docs/PROTOCOL.md §10`). · Soma SSE-C do R2 em cima da cifragem ponta a ponta em PUT/GET único. |
| `OPENBAO_ADDR` | unset · não definida | Enables auto-unseal when set. · Liga o auto-unseal quando definida. |
| `OPENBAO_TOKEN` | unset · não definida | Token scoped to this SDK's own OpenBao path. · Token restrito ao path deste SDK no OpenBao. |
| `OPENBAO_MOUNT` | `secret` | KV v2 mount point. · Ponto de montagem do KV v2. |
| `OPENBAO_PATH_PREFIX` | `diagnos` | Prefix of the saved-state path. · Prefixo do path do estado salvo. |
| `OPENBAO_NAMESPACE` | unset · não definida | OpenBao Enterprise namespace, if any. · Namespace do OpenBao Enterprise, se houver. |
| `OPENBAO_TOKEN_FILE` | unset · não definida | A file holding the OpenBao token, read when `OPENBAO_TOKEN` is unset (what Kubernetes/Compose mount). · Um arquivo com o token do OpenBao, lido quando `OPENBAO_TOKEN` não está definida (o que Kubernetes/Compose montam). |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` refuses to start if a secret cannot be locked in RAM. · `require` se recusa a subir se um segredo não puder ser travado na RAM. |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` skips disabling core dumps / `ptrace` at unlock (debugging only). · `0` pula desligar core dumps / `ptrace` no unlock (só para depurar). |

🇺🇸 Everything above can also be set explicitly, bypassing the environment
entirely: `Diagnos(settings=Settings(api_token="apikey-…", vault_url=..., sse_c=True))`.
🇧🇷 Tudo acima também pode ser definido de forma explícita, sem passar pelo
ambiente: `Diagnos(settings=Settings(api_token="apikey-…", vault_url=..., sse_c=True))`.

## What this SDK never does · O que este SDK nunca faz

- 🇺🇸 **Never sends a key to the vault.** Group DEKs, document DEKs, node
  keys, the SDK's own key pair — all of it is generated or opened locally
  and never leaves the process except sealed (enrollment) or, if you opt
  into auto-unseal, into OpenBao.
  🇧🇷 **Nunca manda uma chave para o cofre.** DEKs de grupo, DEKs de
  documento, chaves de nó, o par de chaves do próprio SDK — tudo é gerado ou
  aberto localmente e nunca sai do processo, exceto selado (enrollment) ou,
  se você optar pelo auto-unseal, para o OpenBao.
- 🇺🇸 **Never inspects a signed URL beyond using it.** A presigned `PUT`/`GET`
  URL from the vault is opaque; the SDK sends exactly the bytes and headers
  the protocol calls for and nothing more.
  🇧🇷 **Nunca inspeciona uma URL assinada além de usá-la.** Uma URL de
  `PUT`/`GET` pré-assinada do cofre é opaca; o SDK manda exatamente os bytes
  e headers que o protocolo pede, nada mais.
- 🇺🇸 **Never persists plaintext.** Decrypted records and file bytes exist
  only in the caller's own variables; the SDK itself keeps no cache, no
  temp-file copy of a completed download.
  🇧🇷 **Nunca persiste texto claro.** Registros e bytes de arquivo decifrados
  existem só nas variáveis de quem chama; o SDK em si não guarda cache, nem
  cópia em arquivo temporário de um download terminado.
- 🇺🇸 **Never `repr`s a secret.** `Settings`, `ServiceAccountToken`,
  `SessionKeys`, `Keyring`, `Diagnos` itself — every `__repr__` in this
  codebase is redacted; see `CONVENTIONS.md`.
  🇧🇷 **Nunca dá `repr` de segredo.** `Settings`, `ServiceAccountToken`,
  `SessionKeys`, `Keyring`, o próprio `Diagnos` — todo `__repr__` deste
  código é redigido; veja `CONVENTIONS.md`.
- 🇺🇸 **Never holds a key as a Python object.** Keys are `SecretBox`es in
  locked native memory (see "Where secrets live"); the only clear-text
  export is the OpenBao save you opt into, and even that zeroes its buffers
  the moment the request is built.
  🇧🇷 **Nunca segura uma chave como objeto Python.** Chaves são
  `SecretBox`es em memória nativa travada (veja "Onde os segredos moram"); a
  única exportação em claro é o save no OpenBao que você opta por fazer, e
  mesmo esse zera os buffers assim que a requisição é montada.

## A note on entropy · Uma nota sobre entropia

🇺🇸 Every signed response from the vault carries an `X-Session-Seed`: a fresh
32 bytes, sealed to this session, that this SDK mixes into its own randomness
(`SHA-256(os.urandom(32) ‖ seed)`) before generating the next DEK, node key or
nonce. It never *replaces* `os.urandom` — a process that never received a
seed still gets ordinary OS randomness — it only adds a source the vault
contributes and a sibling process (say, two containers cloned from the same
image, booted before either re-seeded from hardware entropy) does not share.
You never configure this; it happens on every `Diagnos` instance automatically.

🇧🇷 Toda resposta assinada do cofre carrega um `X-Session-Seed`: 32 bytes
novos, selados para esta sessão, que o SDK mistura à própria aleatoriedade
(`SHA-256(os.urandom(32) ‖ seed)`) antes de gerar a próxima DEK, chave de nó
ou nonce. Isso nunca *substitui* o `os.urandom` — um processo que nunca
recebeu uma semente ainda tem aleatoriedade comum do SO — só soma uma fonte
que o cofre contribui e que um processo irmão (digamos, dois containers
clonados da mesma imagem, ligados antes de qualquer um se re-semear com
entropia de hardware) não compartilha. Você nunca configura isto; acontece em
toda instância de `Diagnos` automaticamente.

## Development · Desenvolvimento

```sh
uv sync --all-packages                      # 🇺🇸 builds the Rust enclave too (needs cargo) · 🇧🇷 constrói o enclave Rust também (precisa de cargo)
uv run --package diagnos pytest
uv run ruff check sdk && uv run ruff format --check sdk
uv run mypy sdk/src/diagnos
make rust-lint && make rust-test            # 🇺🇸 the enclave (`sdk/native`) · 🇧🇷 o enclave (`sdk/native`)
```

🇺🇸 Installing from PyPI needs no Rust: wheels ship the compiled enclave for
each platform. Building from source needs a stable Rust toolchain
(`rustup`), which `uv sync` invokes through maturin.
🇧🇷 Instalar do PyPI não precisa de Rust: os wheels trazem o enclave
compilado para cada plataforma. Construir do fonte precisa de um toolchain
Rust estável (`rustup`), que o `uv sync` invoca via maturin.

🇺🇸 See `../README.md` for the workspace layout and `../docs/PROTOCOL.md` for
the normative wire contract this package implements.
🇧🇷 Veja `../README.md` para a estrutura do workspace e `../docs/PROTOCOL.md`
para o contrato de fio normativo que este pacote implementa.
