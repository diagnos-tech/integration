# diagnos

[English](README.md) · **Português (Brasil)**

O SDK Python oficial, zero-knowledge, do cofre diagnos (`vault.diagnos.health`).
Pacientes, exames e arquivos são cifrados neste processo, na RAM,
antes de um único byte chegar à rede — o cofre só vê ciphertext, requisições
assinadas e URLs pré-assinadas. Este pacote é o único lugar onde essa
complexidade mora.

> [!NOTE]
> **Situação: prévia 0.1.0.** Enrollment, chaves de sessão, assinatura de
> requisição, relógio, lock, `vault.patients`, `vault.exams` e
> `vault.drives` falam o protocolo atual do cofre e são verificados contra
> ele pelos testes de contrato Pact (`contracts/`). Limites conhecidos:
> [COMPATIBILITY.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.pt-BR.md).

A meta é o seu código poder ler assim:

```python
from diagnos import Diagnos

with Diagnos() as vault:
    for row in vault.patients.list():
        patient = vault.patients.get(row.id)
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
> `pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"`

`DIAGNOS_API_TOKEN` identifica *esta* service account e o workspace dela;
sozinho, ele não desbloqueia nada — veja [Enrollment](#enrollment-o-link-e-o-código) abaixo.

## 30 segundos até o primeiro `list()`

```python
from diagnos import Diagnos

vault = Diagnos()  # lê DIAGNOS_API_TOKEN
vault.unlock()  # imprime link + código de 6 dígitos, espera aprovação

for row in vault.patients.list():
    print(row.id, row.summary.display_name if row.summary else "—")
```

Você nem precisa chamar `unlock()`: na primeira vez que você toca
`vault.patients`, `vault.exams` ou `vault.drives`, o SDK desbloqueia sozinho.
`unlock()` (e esse caminho preguiçoso) são idempotentes — chame quantas
vezes quiser, de quantos lugares quiser. Sem `DIAGNOS_API_TOKEN`, `Diagnos()`
levanta `ConfigError` nomeando a variável, antes de qualquer chamada de rede.

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

O que o passo 2 imprime no `stderr` (o prompt padrão; passe `on_prompt=` para mostrá-lo do seu jeito):

```text
diagnos SDK — enrollment approval needed · aprovação de enrollment necessária

Open this link to approve · Abra este link para aprovar:
  https://…

Code to type · Código para digitar:
  4 8 2 9 1 5

Expires at (unix seconds) · Expira em (segundos unix): 1790000000
```

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

## Pacientes

```python
from datetime import date

from diagnos import PatientRecord

patient = vault.patients.create(
    {"legal_name": "Jane Doe", "display_name": "Jane", "birth_date": date(1990, 1, 31)},  # um dict é validado
    security_group="sg_oncology",  # exatamente um grupo por documento
    tags=["diabetes"],  # rótulos selados de lista/busca, nunca vão em claro
    specialist_ids=["specialist_123"],  # metadado em claro pelo qual o próprio cofre filtra
)

patient = vault.patients.get(patient.id)  # o conteúdo mais novo: um rascunho mais novo do editor web vence
renamed = patient.record.model_copy(update={"display_name": "Jane R."})
patient = vault.patients.update(
    patient.id,
    renamed,  # sempre o registro completo: toda versão é um retrato inteiro
    expected_latest_version_id=patient.index.latest_version_id,  # recusado se alguém salvou no meio-tempo
)

vault.patients.archive(patient.id)  # uma flag, sem versão nova
vault.patients.unarchive(patient.id)
vault.patients.delete(patient.id)  # para a lixeira; o histórico cifrado fica
vault.patients.restore(patient.id)

for row in vault.patients.iter_all(security_group="sg_oncology"):
    print(row.id, row.summary.display_name if row.summary else "—")  # decifrado localmente, sem download
```

- **O que você grava é o que o app web lê.** `PatientRecord` espelha o registro do app web campo a campo. Um campo
  digitado errado (`birthdate`) é recusado com o campo parecido; qualquer outro campo desconhecido é mantido, então um
  ler-modificar-gravar com `model_copy` nunca perde um campo que o app web acrescentou depois deste SDK ser lançado.
- **Datas** (`birth_date`, `exam_date`) aceitam `date`, `datetime` com fuso ou string ISO, e são gravadas como o app
  web grava: um instante UTC. Defina `DIAGNOS_TIME_PRECISION` com a precisão de anonimização do workspace e elas são
  truncadas antes de selar, como o app web faz.
- **Documentos de identidade** (`identifiers`, ex.: CPF) são selados pelo cofre, não pelo SDK: valores existentes
  sobrevivem à ida e volta; um valor em texto claro é recusado. Use `external_id` para um id de outro sistema.
- **Rascunhos**: `get()` devolve o rascunho do editor web quando ele é mais novo que a versão corrente
  (`patient.from_draft`); `include_draft=False` lê só versões confirmadas. O SDK nunca grava rascunhos.

## Exames

```python
from diagnos import ExamRecord

exam = vault.exams.create(
    ExamRecord(title="TC de tórax", modality="CT", exam_date="2026-09-01", report_html="<p>Sem alterações.</p>"),
    patient_id=patient.id,  # obrigatório, em claro no índice — o cofre roteia por ele; o resto é selado
    security_group="sg_oncology",
)

exam = vault.exams.get(exam.id)
print(exam.patient_id, exam.report_status, exam.record.report_html)
```

`report_lexical` é o estado do editor web e a fonte da verdade do laudo; `report_html` é derivado dele para quem lê
sem abrir o editor. Grave os dois ao produzir um laudo que o editor web deva abrir.

## Arquivos e pastas

Todo arquivo (DICOM, imagem, vídeo, PDF) e toda pasta do workspace é um
*nó*. Um nó pertence a um security group — `vault.drives.drive(grupo)`
grava em um — e ler precisa só do id. Cada arquivo ganha a própria chave; o
nome, o conteúdo e a camada SSE-C do R2 são selados do jeito que o app web
sela. Arquivo pequeno sobe num `PUT`, grande em partes cifradas, 100
arquivos por reserva — você nunca escolhe.

```python
from diagnos import UploadSource

drive = vault.drives.drive("sg_oncologia")

folder_id = drive.create_folder("TC 2026-09-01")
node = drive.upload("exames/IM-0001.dcm", exam_id=exam.id, parent_id=folder_id)  # nome e MIME vêm do path
node = drive.upload(b"bytes crus funcionam", name="nota.txt")

nodes = drive.upload_many(
    [UploadSource("lamina_1.jpg"), UploadSource(jpeg_bytes, name="lamina_2.jpg")],
    exam_id=exam.id,
)  # uma reserva para até 100 arquivos; devolvidos na ordem de entrada, prontos

for child in drive.iter_all(parent_id=folder_id):  # ou drive.list(...) para uma página
    print(drive.name_of(child), child.size, child.mime_type)

data = vault.drives.download(node.node_id)  # bytes na RAM
vault.drives.download(node.node_id, "IM-0001.dcm")  # direto para um arquivo, um pedaço na RAM
for chunk in vault.drives.iter_download(node.node_id):  # ou transmita você mesmo
    ...
```

`vault.drives.list()` / `iter_all()` percorrem o workspace inteiro (todo
grupo que esta sessão pode listar) e filtram por `security_group`,
`exam_id`, `parent_id` e `include_pending`. Um arquivo `.dcm` é tipado
`application/dicom`, para o cofre classificá-lo; passe `mime_type=` para
sobrescrever. `name_of()` devolve o que quem subiu selou — o app web guarda
ali um caminho relativo, então nunca grave nele como caminho local sem
pegar o último segmento. Detalhes de fio:
[`docs/PROTOCOL.pt-BR.md`](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.pt-BR.md) §9–§10.

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
| `ConflictError` | uma versão pendente ou mais nova, um replay, ou um upload que nunca chegou ao armazenamento (`UploadIncomplete`) — o SDK já retentou o que é seguro retentar |
| `RateLimitError` | lançado só depois de o próprio backoff do SDK desistir |
| `GroupKeyUnavailable` | este enrollment nunca recebeu a DEK de um grupo que o documento precisa |
| `EnrollmentDeniedError` / `EnrollmentExpiredError` | ninguém aprovou, ou aprovou tarde demais |
| `SessionExpiredError` | nenhuma sessão local viva — chame `unlock()` (de novo) antes de uma chamada assinada |
| `ProtocolError` | o cofre respondeu algo que o protocolo não permite — não adianta retentar; reporte com a versão do SDK |
| `VaultError` | classe base; carrega `code`, `status`, `trace_id` para um chamado de suporte |

Um conflito é uma classe com muitas causas; `code` diz qual. A que você mesmo trata é a atualização perdida:

```python
from diagnos import ConflictError

patient = vault.patients.get(patient_id)
try:
    vault.patients.update(patient_id, edited, expected_latest_version_id=patient.index.latest_version_id)
except ConflictError as exc:
    if exc.code != "DocumentVersionMismatch":
        raise
    ...  # alguém salvou no meio-tempo: leia de novo, reaplique a mudança, atualize de novo
```

## Configuração

| Variável | Padrão | |
|---|---|---|
| `DIAGNOS_API_TOKEN` | — (obrigatória) | O `apikey-<jwt>` que um admin do workspace emitiu. |
| `DIAGNOS_VAULT_URL` | `https://vault.diagnos.health` | Onde o cofre mora. |
| `DIAGNOS_TIMEOUT_SECONDS` | `30` | Timeout HTTP por requisição. |
| `DIAGNOS_TIME_PRECISION` | não definida | A precisão de anonimização do workspace (`month`, `day`, `hour`, `minute`, `second`); as datas são truncadas nela antes de selar. |
| `DIAGNOS_STORAGE_HOSTS` | `diagnosusercontent.com, r2.cloudflarestorage.com` | Hosts (e subdomínios) para onde uma URL de armazenamento pré-assinada pode apontar, só HTTPS; o resto é recusado antes de um byte sair. |
| `OPENBAO_ADDR` | não definida | Liga o auto-unseal quando definida. |
| `OPENBAO_TOKEN` | não definida | Token restrito ao path deste SDK no OpenBao. |
| `OPENBAO_MOUNT` | `secret` | Ponto de montagem do KV v2. |
| `OPENBAO_PATH_PREFIX` | `diagnos` | Prefixo do path do estado salvo. |
| `OPENBAO_NAMESPACE` | não definida | Namespace do OpenBao Enterprise, se houver. |
| `OPENBAO_TOKEN_FILE` | não definida | Um arquivo com o token do OpenBao, lido quando `OPENBAO_TOKEN` não está definida (o que Kubernetes/Compose montam). |
| `DIAGNOS_MEMORY_LOCK` | `best-effort` | `require` se recusa a subir se um segredo não puder ser travado na RAM. |
| `DIAGNOS_HARDEN_PROCESS` | `1` | `0` pula desligar core dumps / `ptrace` no unlock (só para depurar). |

Tudo acima também pode ser definido de forma explícita, sem passar pelo
ambiente: `Diagnos(settings=Settings(api_token="apikey-…", vault_url=..., time_precision="day"))`.

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
