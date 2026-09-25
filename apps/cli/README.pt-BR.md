# diagnos-cli

[English](README.md) · **Português (Brasil)**

A linha de comando `diagnos` — o cofre zero-knowledge diagnos, direto do seu terminal, construída em cima do SDK
[`diagnos`](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.pt-BR.md). Todo byte de criptografia,
assinatura e retentativa mora no SDK; este pacote só interpreta argumentos e renderiza o que o SDK devolve.

> [!NOTE]
> **Ainda não está no PyPI.** O `pipx install diagnos-cli` abaixo é o comando de instalação definitivo, mas até o
> primeiro release, instale a partir do fonte (construir o SDK precisa de um
> [toolchain Rust](https://rustup.rs/); `cli` depende do SDK `diagnos`, que também ainda não foi publicado, então os
> dois vêm do git num único comando):
> ```sh
> pipx install "diagnos-cli @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/cli" \
>   --preinstall "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"
> ```
> Vem do `imgexam-cli`? As versões recomeçam em `0.1.0` sob o nome novo — leia o
> [MIGRATING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.pt-BR.md) antes de
> atualizar.

## Instalação

```sh
pipx install diagnos-cli
export DIAGNOS_API_TOKEN="apikey-…"   # emitido por um admin do workspace
```

Auto-unseal via OpenBao precisa do extra `openbao`: `pipx install "diagnos-cli[openbao]"` — veja
[OpenBao, para servidores](#openbao-para-servidores) abaixo.

`DIAGNOS_API_TOKEN` identifica *esta* service account e o workspace dela; sozinho, ele não desbloqueia nada — é para
isso que serve o `diagnos login`. `--token` em qualquer comando o sobrescreve só para aquela invocação, e nunca é
ecoado em lugar nenhum (nem no `--help`, nem na saída, nem no `--json`).

## Seu primeiro `diagnos login`

```sh
$ diagnos login
```

Na primeira vez que um processo `diagnos` roda (e em toda vez depois, a menos que o OpenBao esteja configurado — veja
abaixo), ele precisa fazer *enrollment*. O `login` roda essa dança de forma explícita, para você ver acontecer:
aparece um painel com um link e um código de 6 dígitos, depois um spinner enquanto espera.

```
╭────────────────────── diagnos · enrollment ───────────────────────╮
│ Open this link and type the code below to approve this session.   │
│ Abra este link e digite o código abaixo para aprovar esta sessão. │
│                                                                   │
│ https://…                                                         │
│                                                                   │
│   4  8  2  9  1  5                                                │
╰───────────────────────────────────────────────────────────────────╯
⠋ waiting for approval… · aguardando aprovação…
```

Esse painel — e a linha de status embaixo dele — de fato saem nas duas línguas, em toda instalação: é a transcrição
literal da saída do `rich`, não uma escolha de tradução deste documento.

Abra o link, digite o código, e escolha quais security groups este processo da CLI pode ler. Assim que um admin do
workspace aprova, o `login` imprime o que foi concedido:

```
Enrolled · Sessão estabelecida
  workspace_id: ws_...
  account_id:   acct_...
  groups · grupos: sg_oncology, sg_radiology
```

**A CLI nunca guarda a sessão em disco.** Sem o OpenBao configurado (próxima seção), essa sessão vive só na memória
deste processo — no instante em que ele termina, ela some, e a *próxima* invocação de `diagnos` faz enrollment de
novo, do zero, com link e código novos. Isto não é um bug para contornar: o `login` sozinho serve para *validar um
token e ver o que foi concedido*, um processo por vez. Todo outro comando (`patients`, `exams`, `files`, `groups`)
também faz enrollment sozinho, de forma preguiçosa, se não houver sessão disponível — você não precisa rodar `login`
antes.

## OpenBao, para servidores

Uma aprovação humana a cada reinício é aceitável num script avulso; não é aceitável num cron job ou num pod
Kubernetes. Configure `OPENBAO_ADDR`/`OPENBAO_TOKEN` (veja a seção
[Auto-unseal com OpenBao](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.pt-BR.md#auto-unseal-com-openbao)
do SDK para o tradeoff completo) e o `unlock()` de todo comando salva a sessão no KV cifrado do OpenBao depois de um
enrollment bem-sucedido, e restaura de lá na próxima invocação — sem humano, sem link novo, até a sessão salva em si
expirar. `login --auto-unseal`/`--no-auto-unseal` sobrescreve o padrão automático (ligado se `OPENBAO_ADDR` estiver
definida) só para aquela invocação.

## Comandos

| Comando | Situação | O que faz |
|---|---|---|
| `diagnos login [--auto-unseal/--no-auto-unseal]` | ✅ funciona hoje | Faz enrollment, mostra o que foi concedido. |
| `diagnos status [--check]` | ✅ funciona hoje | Token interpretado, OpenBao, versão do SDK; `--check` também desbloqueia. |
| `diagnos groups` | ✅ funciona hoje | Lista os security groups concedidos. |
| `diagnos session lock` | ✅ funciona hoje | Encerra a sessão, best-effort. |
| `diagnos patients list [--group G] [--include-deleted] [--limit N] [--cursor C] [--all] [--summary]` | ✅ funciona hoje | Pagina pacientes; anônimo a menos que `--summary` decifre nomes e tags. |
| `diagnos patients get PATIENT_ID [--version V] [--committed]` | ✅ funciona hoje | Decifra e mostra um paciente (um rascunho mais novo vence, salvo com `--committed`). |
| `diagnos patients create --group G (--file record.json \| --legal-name ... --display-name ... [--birth-date D] [--external-id X]) [--tag T]...` | ✅ funciona hoje | Cria um paciente. |
| `diagnos patients update PATIENT_ID --file record.json [--tag T]... [--expect-version V]` | ✅ funciona hoje | Versão nova e completa; `--tag` substitui as tags, `--expect-version` recusa gravação desatualizada. |
| `diagnos patients archive\|unarchive PATIENT_ID` | ✅ funciona hoje | Vira a flag de arquivado (sem versão nova). |
| `diagnos patients delete PATIENT_ID [--yes]` | ✅ funciona hoje | Manda o paciente para a lixeira (`--yes` pula a confirmação). |
| `diagnos patients restore PATIENT_ID` | ✅ funciona hoje | Tira o paciente da lixeira. |
| `diagnos exams list [--group G] [--include-deleted] [--limit N] [--cursor C] [--all] [--summary]` | ✅ funciona hoje | Pagina exames; anônimo a menos que `--summary` decifre título, modalidade e data. |
| `diagnos exams get EXAM_ID [--version V] [--committed]` | ✅ funciona hoje | Decifra e mostra um exame, o laudo como texto puro. |
| `diagnos exams create --patient P --group G (--file record.json \| --title T [--modality M] [--exam-date D])` | ✅ funciona hoje | Cria um exame; só `--patient` vai em claro. |
| `diagnos exams update EXAM_ID --file record.json [--expect-version V]` | ✅ funciona hoje | Versão nova e completa do registro. |
| `diagnos exams archive\|unarchive EXAM_ID` | ✅ funciona hoje | Vira a flag de arquivado (sem versão nova). |
| `diagnos exams delete EXAM_ID [--yes]` | ✅ funciona hoje | Manda o exame para a lixeira (`--yes` pula a confirmação). |
| `diagnos exams restore EXAM_ID` | ✅ funciona hoje | Tira o exame da lixeira. |
| `diagnos files list [--group G] [--folder F] [--exam E] [--include-pending] [--limit N] [--cursor C] [--all]` | ✅ funciona hoje | Lista arquivos e pastas, nomes decifrados — o workspace inteiro, salvo filtro. |
| `diagnos files upload --group G PATH... [--exam E] [--folder F]` | ✅ funciona hoje | Cifra e sobe, 100 arquivos por reserva; arquivos grandes sobem por partes. |
| `diagnos files mkdir NOME --group G [--parent F]` | ✅ funciona hoje | Cria uma pasta e imprime o id do nó (passe-o para `--folder`). |
| `diagnos files download NODE_ID [-o DEST]` | ✅ funciona hoje | Baixa e decifra, por padrão com o nome do próprio arquivo (só o último segmento do caminho). |
| `diagnos files get NODE_ID` | ✅ funciona hoje | Metadado e nome decifrado de um arquivo. |

Ler um arquivo precisa só do id do nó; o cofre sabe a que grupo ele pertence.
Limites conhecidos e as questões ainda em aberto do lado do cofre:
[Compatibilidade com o cofre](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.pt-BR.md).

Opções globais, no comando raiz, antes do subcomando:

| Opção | O que faz |
|---|---|
| `--json` | Saída para máquina, sem tabelas/painéis/spinners. |
| `--quiet` / `-q` | Suprime spinners e barras de progresso. |
| `--vault-url URL` | Sobrescreve `DIAGNOS_VAULT_URL`. |
| `--token TOKEN` | Sobrescreve `DIAGNOS_API_TOKEN`; nunca ecoado. |
| `--no-color` | Desliga cores ANSI. |
| `--version` | Imprime a versão da CLI e sai. |

## `--json`, para scripts

Todo comando aceita `--json` antes do nome do subcomando — a saída é `json.dumps` puro, nunca envolvida pelo `rich`,
então um campo longo nunca quebra uma linha no meio do jeito que um renderizador ciente da largura do terminal
poderia:

```sh
diagnos --json patients list --group sg_oncology | jq '.items[].document_id'
```

## Códigos de saída

Estáveis e documentados, para `if`/`case` num script — nunca faça grep do texto do erro:

| Código | Significado |
|---|---|
| `0` | Sucesso |
| `1` | Outro erro (inclui entrada inválida, ex.: `ValidationError`). |
| `2` | Erro de configuração (token ausente/malformado, variável de ambiente). |
| `3` | Autenticação/permissão/sessão (`AuthenticationError`, `DiagnosPermissionError`, `GroupKeyUnavailable`, `SessionExpiredError`, enrollment negado/expirado). |
| `4` | Não encontrado. |
| `5` | Cota excedida. |
| `6` | Limite de taxa. |
| `7` | Conflito (versão pendente ou mais nova, replay, um upload que nunca chegou ao armazenamento). |

## Desenvolvimento

```sh
uv sync --all-packages
uv run --package diagnos-cli pytest apps/cli/tests -q
uv run ruff check cli && uv run ruff format --check cli
uv run mypy apps/cli/src
```

Veja o [CONTRIBUTING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.pt-BR.md) para
a regra de docstring bilíngue e a fronteira "`cli` importa só `diagnos`", e o
[README do workspace](https://github.com/diagnos-tech/integration/blob/develop/README.pt-BR.md) para a estrutura
geral e os alvos de `make` (`sync`, `test`, `check`, `help`) que quem contribui usa.
