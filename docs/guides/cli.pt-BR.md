# Guia da CLI

[English](cli.md) · **Português (Brasil)**

`diagnos` é o SDK no seu terminal: o mesmo enrollment, a mesma cifragem, os mesmos erros, com tabelas legíveis por
padrão e JSON para scripts. Todo comando está listado com todas as opções na [referência da CLI](../reference/cli.json);
este guia é sobre usá-los em conjunto.

```sh
diagnos --help                  # todo comando
diagnos patients create --help  # um comando, com exemplos no fim
```

## Opções globais

Opções globais vêm **antes** do subcomando — `diagnos --json patients list`, não `diagnos patients list --json`.

| Opção | O que faz |
|---|---|
| `--json` | saída para máquina: JSON puro em `stdout`, sem tabelas, painéis ou spinners |
| `--quiet`, `-q` | sem spinners nem barras de progresso |
| `--token TOKEN` | sobrescreve `DIAGNOS_API_TOKEN` nesta invocação; nunca é ecoado em lugar nenhum |
| `--vault-url URL` | sobrescreve `DIAGNOS_VAULT_URL` nesta invocação |
| `--no-color` | sem cores ANSI (a variável de ambiente `NO_COLOR` também) |
| `--version` | imprime a versão da CLI e sai |

Todo o resto — timeouts, precisão de datas, OpenBao — vem do ambiente, exatamente como no SDK
([Configuração](configuration.pt-BR.md)).

## Enrollment no terminal

Cada invocação do `diagnos` é um processo próprio, e um processo precisa de uma sessão aprovada antes de decifrar
qualquer coisa. O primeiro comando que precisa de uma mostra um painel em `stderr` e espera:

```text
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

Um admin abre o link, confere a máquina descrita ali, digita o código e escolhe os grupos. O `login` faz só isso, e
depois mostra o que foi concedido:

```sh
diagnos login
diagnos --json login | jq -r '.security_groups[]'
```

```text
Enrolled · Sessão estabelecida
  workspace_id: ws_...
  account_id:   acct_...
  groups · grupos: sg_oncology, sg_radiology
```

`status` lê o token localmente e informa o OpenBao e o enclave de memória sem tocar a rede; `status --check` também
desbloqueia e lista os grupos concedidos, e `groups` os lista um por linha.

```sh
diagnos status
diagnos status --check
diagnos groups
```

### Sem aprovar todo comando

Sem OpenBao, **a sessão morre com o processo**: a invocação seguinte faz enrollment de novo, com link e código novos.
É o padrão certo num notebook — `login` serve para conferir um token e ver o que ele concede. Para qualquer coisa que
rode sem ninguém olhando, configure o [auto-unseal com OpenBao](sessions.pt-BR.md#auto-unseal-com-openbao): a primeira
invocação faz enrollment uma vez e salva a sessão, e toda posterior a restaura em silêncio até ela expirar.

```sh
export OPENBAO_ADDR="https://openbao.internal:8200"
export OPENBAO_TOKEN_FILE=/run/secrets/openbao-token
diagnos login                    # uma pessoa aprova uma vez; a sessão é salva no OpenBao
diagnos --quiet patients list    # restaurada — sem prompt
diagnos login --no-auto-unseal   # enrollment sem salvar, mesmo com OPENBAO_ADDR definida
```

`diagnos session lock` encerra a sessão: apaga a cópia salva no OpenBao, então a invocação seguinte faz enrollment de
novo.

## Pacientes

As listas são **anônimas por padrão** — ids, versões, grupos e flags — para uma lista nunca imprimir nomes que você
não pediu. `--summary` decifra os nomes e as tags de cada linha; `get` imprime o registro inteiro.

```sh
diagnos patients list --group sg_oncology            # uma página, anônima
diagnos patients list --group sg_oncology --summary  # nomes e tags também
diagnos patients list --all                          # todas as páginas
diagnos patients list --limit 20 --cursor CURSOR     # a próxima página; o cursor é impresso embaixo de cada página
diagnos patients list --include-deleted              # a lixeira também
diagnos patients get PATIENT_ID                      # o conteúdo mais novo: um rascunho do editor web mais novo vence
diagnos patients get PATIENT_ID --committed          # só versões salvas
diagnos patients get PATIENT_ID --version VERSION_ID # uma versão exata
```

Crie a partir de flags inline, ou de um arquivo JSON com o registro completo:

```sh
diagnos patients create --group sg_oncology --legal-name "Maria da Silva" --display-name Maria \
  --birth-date 1990-01-31 --external-id MRN-0042 --tag diabetes --tag retorno
diagnos patients create --group sg_oncology --file patient.json
```

```json
{
  "legal_name": "Maria da Silva",
  "display_name": "Maria",
  "birth_date": "1990-01-31",
  "biological_sex": "FEMALE",
  "address": { "city": "São Paulo", "state": "SP", "country": "BR" }
}
```

Uma atualização grava uma versão nova e completa a partir de um arquivo. `--expect-version` faz o cofre recusá-la se
alguém salvou no meio-tempo (código de saída `7`); `--tag` substitui as tags, e omiti-la as mantém:

```sh
diagnos --json patients get PATIENT_ID | jq '.record' > patient.json   # leia
$EDITOR patient.json                                                    # mude
diagnos patients update PATIENT_ID --file patient.json --expect-version VERSION_ID   # grave
```

Arquivar e apagar são flags; apagar pede confirmação a menos que `--yes`, e nunca é apagar de verdade:

```sh
diagnos patients archive PATIENT_ID
diagnos patients unarchive PATIENT_ID
diagnos patients delete PATIENT_ID --yes
diagnos patients restore PATIENT_ID
```

Os campos do registro, as datas e a proteção contra erro de digitação são os do SDK — veja
[Pacientes](patients.pt-BR.md#o-registro).

## Exames

Os mesmos verbos, com duas diferenças: `create` precisa do paciente, o único campo que viaja em claro, e `get` imprime
o laudo como texto puro (`--json` traz o registro completo, com o HTML).

```sh
diagnos exams list --group sg_radiology --summary
diagnos exams create --patient PATIENT_ID --group sg_radiology \
  --title "TC de tórax" --modality CT --exam-date 2026-09-01
diagnos exams create --patient PATIENT_ID --group sg_radiology --file exam.json
diagnos exams get EXAM_ID
diagnos exams update EXAM_ID --file exam.json --expect-version VERSION_ID
diagnos exams delete EXAM_ID --yes
```

Grave `report_lexical` e `report_html` no `exam.json` quando pessoas vão abrir o laudo no editor web —
[Exames](exams.pt-BR.md#o-laudo) explica por quê.

## Arquivos

```sh
diagnos files upload --group sg_oncology --exam EXAM_ID scans/*.dcm   # vários de uma vez, 100 por reserva
FOLDER=$(diagnos --json files mkdir "TC 2026-09-01" --group sg_oncology | jq -r .node_id)
diagnos files upload --group sg_oncology --folder "$FOLDER" report.pdf
diagnos files list --group sg_oncology --folder "$FOLDER"             # nomes decifrados
diagnos files list --exam EXAM_ID --all
diagnos files list --include-pending                                  # uploads inacabados também
diagnos files get NODE_ID                                             # metadado e nome, nunca o conteúdo
diagnos files download NODE_ID                                        # para ./<o nome dele>
diagnos files download NODE_ID -o scan.dcm
```

`download` sem `-o` grava com o nome decifrado do arquivo no diretório atual — **só o último segmento do caminho**,
porque o app web sela caminhos relativos como nomes e um `../../.bashrc` forjado não pode escapar. Ler um arquivo só
precisa do id do nó; `--group` no `list` é um filtro, não uma exigência.

## Scripts

### Saída JSON

Com `--json`, o `stdout` é exatamente um documento JSON — nunca embrulhado nem colorido pelo renderizador do terminal,
então um campo longo não quebra linha. As formas batem com as da API REST:

| Comando | `stdout` |
|---|---|
| `patients list`, `exams list` | `{"items": [{"index": …, "summary": null ou …}], "next_cursor": …}` |
| `patients get`, `exams get`, `create`, `update` | o `Patient` / `Exam` inteiro: `index`, `record`, `summary`, `version_id`, `draft_rev` |
| `archive`, `unarchive`, `delete`, `restore` | o `index` atualizado |
| `files list`, `files upload` | `{"items": [{"node": …, "name": …}], "next_cursor": …}` |
| `files get` | `{"node": …, "name": …}` |
| `files mkdir` | `{"node_id": …}` |
| `files download` | `{"node_id": …, "saved_to": …}` |
| `login` | `{"workspace_id": …, "account_id": …, "security_groups": […]}` |
| `groups` | `{"security_groups": […]}` |
| `status` | `workspace_id`, `account_id`, `openbao_configured`, `sdk_version`, `memory` — e `security_groups` com `--check` |

```sh
diagnos --json patients list --all | jq -r '.items[].index.document_id'
diagnos --json exams list --all | jq -r '.items[] | select(.index.meta.patient_id == "PATIENT_ID") | .index.document_id'
diagnos --json files list --exam EXAM_ID --all | jq -r '.items[] | "\(.node.node_id)\t\(.name)"'
```

Erros nunca vão para o `stdout`: vão para o `stderr` numa linha, e o código de saída diz o que aconteceu.

### Códigos de saída

`0` é sucesso; `2` um problema de configuração; `3` autenticação, permissão, sessão ou enrollment; `4` não encontrado;
`5` cota; `6` limite de taxa; `7` conflito; `1` qualquer outra coisa. O mapeamento completo de cada exceção do SDK está
em [Erros](errors.pt-BR.md#toda-exceção).

### Tarefas sem ninguém olhando

```sh
#!/bin/sh
# nightly-upload.sh — rodado pelo cron, com OPENBAO_ADDR e OPENBAO_TOKEN_FILE no ambiente
set -eu
diagnos --quiet --no-color files upload --group sg_radiology --exam "$EXAM_ID" /data/outbox/*.dcm
```

Use `--quiet` para nenhum spinner escrever no log, OpenBao para nenhuma execução esperar uma pessoa, e o código de
saída — não o texto — para decidir o que aconteceu.
