# diagnos

[English](README.md) · **Português (Brasil)**

O SDK Python oficial, zero-knowledge, do cofre diagnos (`vault.diagnos.health`).
Pacientes, exames e arquivos de drive são cifrados neste processo, na RAM,
antes de um único byte chegar à rede — o cofre só vê ciphertext, requisições
assinadas e URLs pré-assinadas. Este pacote é o único lugar onde essa
complexidade mora.

> [!WARNING]
> **Situação: prévia 0.1.0.** Enrollment, chaves de sessão, assinatura de
> requisição, relógio e lock são verificados contra o cofre pelos testes de
> contrato Pact (`contracts/`). `vault.patients`, `vault.exams` e
> `vault.drives`, logo abaixo, ainda implementam uma **revisão anterior** do
> protocolo do cofre e ainda não são compatíveis com o `vault.diagnos.health`
> — leia
> [COMPATIBILITY.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.pt-BR.md)
> antes de construir em cima deles. Eles continuam documentados aqui,
> rotulados **prévia**, para o formato da API poder ser revisado.

A meta é o seu código poder ler assim:

```python
from diagnos import Diagnos

with Diagnos() as vault:
    for index in vault.patients.list():
        patient = vault.patients.get(index.document_id)
        print(patient.record.legal_name)
```

## Instalação

```sh
pip install diagnos
export DIAGNOS_API_TOKEN="apikey-…"   # emitido por um admin do workspace
```

> [!NOTE]
> Ainda não está no PyPI. Até o primeiro release, instale do fonte
> (construir o enclave exige um [toolchain Rust](https://rustup.rs/)):
> `pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=sdk"`

`DIAGNOS_API_TOKEN` identifica *esta* service account e o workspace dela;
sozinho, ele não desbloqueia nada — veja [Enrollment](#enrollment-o-link-e-o-código) abaixo.

## 30 segundos até o primeiro `list()`

```python
from diagnos import Diagnos

vault = Diagnos()  # lê DIAGNOS_API_TOKEN
vault.unlock()  # imprime link + código de 6 dígitos, espera aprovação

for index in vault.patients.list():
    print(index.document_id, index.updated_at)
```

Você nem precisa chamar `unlock()`: na primeira vez que você toca
`vault.patients`, `vault.exams` ou `vault.drives`, o SDK desbloqueia sozinho.
`unlock()` (e esse caminho preguiçoso) são idempotentes — chame quantas
vezes quiser, de quantos lugares quiser.

## Enrollment: o link e o código

Na primeira vez que um processo do SDK roda (e em toda vez depois, a menos
que o auto-unseal esteja configurado — veja abaixo), ele precisa fazer
*enrollment*:

1. Gera um par de chaves híbrido (X25519 + ML-KEM-768) na RAM e o registra no
   cofre, junto com uma descrição de onde está rodando (SO, container,
   hostname, usuário) — para quem aprova reconhecer a máquina que está
   pedindo.
2. Imprime um link e um código de 6 dígitos em `stderr`. Um admin do
   workspace abre o link no app web do diagnos, lê a descrição do runtime,
   digita o código, e escolhe quais security groups este processo do SDK
   pode ler.
3. O app web sela as DEKs desses grupos **para as chaves públicas do SDK**; o
   cofre sela as chaves de sessão do mesmo jeito. O SDK faz poll, abre as
   duas com as chaves privadas que nunca saíram do processo, e fica
   desbloqueado.

Até uma pessoa aprovar, `unlock()` bloqueia. Não existe atalho para esse
passo — é o modelo de segurança inteiro, não um atrito para contornar.

```python
from diagnos import Diagnos, EnrollmentPrompt


def show_prompt(prompt: EnrollmentPrompt) -> None:
    print(f"Abra {prompt.approval_url} e digite {prompt.code}")


vault = Diagnos(on_prompt=show_prompt)  # o prompt padrão já imprime em stderr
vault.unlock()
```

## Auto-unseal com OpenBao

Uma aprovação humana a cada reinício é aceitável num script de notebook;
não é aceitável num pod Kubernetes ou num cron job. Defina
`OPENBAO_ADDR`/`OPENBAO_TOKEN` e o SDK salva o estado desbloqueado (chaves de
sessão, DEKs de grupo, o par de chaves do próprio SDK) no KV cifrado do
OpenBao logo depois de um enrollment bem-sucedido, e restaura de lá na
próxima subida — sem humano, até a sessão salva em si expirar.

**O tradeoff, sem rodeios**: isso move suas DEKs de grupo de "só na RAM
deste processo" para "também no armazenamento do OpenBao, em
`<OPENBAO_PATH_PREFIX>/<workspace_id>/<account_id>`". Quem conseguir ler
aquele único path decifra exatamente o que este processo do SDK decifra.
Restrinja o token do OpenBao a esse path e nada mais amplo — é isso que
mantém isto uma troca intencional, não um vazamento silencioso.

```sh
pip install "diagnos[openbao]"
export OPENBAO_ADDR="https://openbao.internal:8200"
export OPENBAO_TOKEN="…"           # restrito a este único path
```

```python
vault = Diagnos()  # auto_unseal é True por padrão assim que OPENBAO_ADDR está definida
vault.unlock()  # restaura em silêncio se havia sessão válida salva; senão, faz enrollment
```

## Onde os segredos moram

Toda chave que este SDK segura — chaves de sessão, a DEK de cada security
group, a DEK de cada documento, a própria identidade X25519 + ML-KEM-768 do
SDK — vive numa extensão Rust pequena embarcada no wheel, `diagnos._secure`
(`native/`). Uma chave lá é um `SecretBox`: bytes em memória travada na RAM
(`mlock`, nunca vai ao swap), excluída de core dumps, cercada por guard
pages, zerada num filho de `fork()` e zerada no instante em que a caixa é
descartada. Ela nunca volta ao Python como `bytes` — assinar uma requisição,
abrir uma semente, desembrulhar a chave de um documento, cifrar um arquivo
acontecem dentro da extensão. Desbloquear uma sessão também endurece o
processo: core dumps desligados, attach de `ptrace` negado. Nada disso muda
como você usa o SDK; muda o que um atacante com um arquivo de swap, um core
dump ou um debugger consegue encontrar.

Travar memória conta contra `ulimit -l` (muitas vezes 64 KiB em containers).
Quando o kernel recusa, o SDK mantém toda outra proteção, registra em log e
emite um `MemoryLockWarning`; defina `DIAGNOS_MEMORY_LOCK=require` para se
recusar a rodar assim. Para um container sem root travar memória, conceda
`CAP_IPC_LOCK` (veja
[`apps/api/deploy/README.md`](https://github.com/diagnos-tech/integration/blob/develop/apps/api/deploy/README.pt-BR.md)).
[`native/README.pt-BR.md`](native/README.pt-BR.md) diz exatamente o que é e
o que não é garantido.

## Pacientes (prévia)

```python
from diagnos import PatientRecord

patient = vault.patients.create(
    {
        "legal_name": "Jane Doe",
        "display_name": "Jane",
    },  # um dict é validado para você
    security_group="sg_oncology",
    specialist_ids=["specialist_123"],
)

patient = vault.patients.get(patient.id)
patient = vault.patients.update(patient.id, PatientRecord(legal_name="Jane R. Doe", display_name="Jane"))

vault.patients.archive(patient.id)
vault.patients.unarchive(patient.id)
vault.patients.delete(patient.id)  # marca o índice; o histórico cifrado permanece

for index in vault.patients.iter_all(security_group="sg_oncology"):
    ...
```

## Exames (prévia)

```python
from diagnos import ExamRecord

exam = vault.exams.create(
    ExamRecord(title="Chest CT", report={"format": "text", "content": "unremarkable"}),
    patient_id=patient.id,  # obrigatório, em claro no índice — o cofre roteia por ele
    security_group="sg_oncology",
    modality="CT",
)

exam = vault.exams.get(exam.id)
print(exam.patient_id, exam.record.report.content)
```

## Drives — arquivos (prévia)

Um drive é um security group; todo arquivo dentro dele (DICOM, imagem,
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
)  # uma única chamada de reserva para o lote inteiro

data = drive.download(node.node_id)  # bytes na RAM
drive.download(node.node_id, "downloaded_ct.dcm")  # direto para um arquivo

for node in drive.list(exam_id=exam.id):
    print(drive.name_of(node), node.size)
```

`upload`/`upload_many` decidem single ou multipart por você, a partir do
tamanho do arquivo
([`docs/PROTOCOL.pt-BR.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.pt-BR.md)
§9) — nada para escolher.

## Erros

Toda exceção é alcançável a partir de `diagnos` — capture por classe, nunca
por mensagem
([`docs/PROTOCOL.pt-BR.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.pt-BR.md)
§12):

| Classe | Quando |
|---|---|
| `ValidationError` | a requisição em si está errada |
| `AuthenticationError` | token/sessão/assinatura recusados — em geral, refaça o enrollment |
| `QuotaError` | o workspace não tem crédito para isto |
| `DiagnosPermissionError` | esta service account não pode fazer isto aqui |
| `NotFoundError` | 404 |
| `ConflictError` | uma versão pendente ou um replay — o SDK já retentou o que é seguro retentar |
| `RateLimitError` | lançado só depois de o próprio backoff do SDK desistir |
| `GroupKeyUnavailable` | este enrollment nunca recebeu a DEK de um grupo que o documento precisa |
| `EnrollmentDeniedError` / `EnrollmentExpiredError` | ninguém aprovou, ou aprovou tarde demais |
| `SessionExpiredError` | nenhuma sessão local viva — chame `unlock()` (de novo) antes de uma chamada assinada |
| `VaultError` | classe base; carrega `code`, `status`, `trace_id` para um chamado de suporte |

## Configuração

| Variável | Padrão | |
|---|---|---|
| `DIAGNOS_API_TOKEN` | — (obrigatória) | O `apikey-<jwt>` que um admin do workspace emitiu. |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | Onde o cofre mora. |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | Timeout HTTP por requisição. |
| `DIAGNOS_SSE_C` | desligado | Soma SSE-C do R2 em cima da cifragem ponta a ponta em PUT/GET único ([`docs/PROTOCOL.pt-BR.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.pt-BR.md) §10). |
| `OPENBAO_ADDR` | não definida | Liga o auto-unseal quando definida. |
| `OPENBAO_TOKEN` | não definida | Token restrito ao path deste SDK no OpenBao. |
| `OPENBAO_MOUNT` | `secret` | Ponto de montagem do KV v2. |
| `OPENBAO_PATH_PREFIX` | `diagnos` | Prefixo do path do estado salvo. |
| `OPENBAO_NAMESPACE` | não definida | Namespace do OpenBao Enterprise, se houver. |
| `OPENBAO_TOKEN_FILE` | não definida | Um arquivo com o token do OpenBao, lido quando `OPENBAO_TOKEN` não está definida (o que Kubernetes/Compose montam). |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` se recusa a subir se um segredo não puder ser travado na RAM. |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` pula desligar core dumps / `ptrace` no unlock (só para depurar). |

Tudo acima também pode ser definido de forma explícita, sem passar pelo
ambiente: `Diagnos(settings=Settings(api_token="apikey-…", vault_url=..., sse_c=True))`.

## O que este SDK nunca faz

- **Nunca manda uma chave para o cofre.** DEKs de grupo, DEKs de
  documento, chaves de nó, o par de chaves do próprio SDK — tudo é gerado ou
  aberto localmente e nunca sai do processo, exceto selado (enrollment) ou,
  se você optar pelo auto-unseal, para o OpenBao.
- **Nunca inspeciona uma URL assinada além de usá-la.** Uma URL de
  `PUT`/`GET` pré-assinada do cofre é opaca; o SDK manda exatamente os bytes
  e headers que o protocolo pede, nada mais.
- **Nunca persiste texto claro.** Registros e bytes de arquivo decifrados
  existem só nas variáveis de quem chama; o SDK em si não guarda cache, nem
  cópia em arquivo temporário de um download terminado.
- **Nunca dá `repr` de segredo.** `Settings`, `ServiceAccountToken`,
  `SessionKeys`, `Keyring`, o próprio `Diagnos` — todo `__repr__` deste
  código é redigido.
- **Nunca segura uma chave como objeto Python.** Chaves são `SecretBox`es
  em memória nativa travada (veja "Onde os segredos moram"); a única
  exportação em claro é o save no OpenBao que você opta por fazer, e mesmo
  esse zera os buffers assim que a requisição é montada.

## Uma nota sobre entropia

Toda resposta a uma requisição assinada leva um `random_seed` no envelope
JSON: 32 bytes novos, selados para esta sessão, que o SDK mistura à própria
aleatoriedade antes de gerar a próxima DEK, chave de nó ou nonce. Isso nunca
*substitui* o `os.urandom` — um processo que nunca recebeu uma semente ainda
tem aleatoriedade comum do SO — só soma uma fonte que o cofre contribui e
que um processo irmão (digamos, dois containers clonados da mesma imagem,
ligados antes de qualquer um se re-semear com entropia de hardware) não
compartilha. Você nunca configura isto; acontece em toda instância de
`Diagnos` automaticamente.

## Desenvolvimento

```sh
make sync                       # instala tudo e constrói o enclave Rust (precisa de cargo)
uv run --package diagnos pytest apps/sdk/tests
make lint                       # ruff, cargo fmt/clippy, docs
make types                      # mypy --strict
```

Rode `make help` na raiz do repositório para ver todos os alvos. Instalar
do PyPI não precisa de Rust: os wheels trazem o enclave compilado para cada
plataforma (abi3, CPython ≥ 3.11). Construir do fonte precisa de um
toolchain Rust estável (`rustup`), que o `uv sync` invoca via maturin.

Veja [`../README.md`](https://github.com/diagnos-tech/integration/blob/develop/README.pt-BR.md)
para a estrutura do workspace e
[`docs/PROTOCOL.pt-BR.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.pt-BR.md)
para o contrato de fio normativo que este pacote implementa.
