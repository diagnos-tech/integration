# Guia da CLI

[English](cli.md) · **Português (Brasil)**

`diagnos` é o SDK no seu terminal: o mesmo token, a mesma cifragem, os mesmos erros, com tabelas legíveis por
padrão e JSON para scripts. Todo comando está listado com todas as opções na [referência da CLI](../reference/cli.json);
este guia é sobre usá-los em conjunto.

```sh
diagnos --help                  # todo comando
diagnos patients create --help  # um comando, com exemplos no fim
```

## Opções globais

Opções globais vão em **qualquer lugar** da linha — `diagnos patients list --json` é `diagnos --json patients list`.
Só o que vem depois de `--` fica intocado.

| Opção | O que faz |
|---|---|
| `--json` | saída para máquina: JSON puro em `stdout`, sem tabelas, painéis ou spinners |
| `--quiet`, `-q` | sem spinners nem barras de progresso |
| `--token TOKEN` | o token desta única invocação (um token `dgn_sk1_`, ou o `apikey-` obsoleto), sobrescrevendo toda outra fonte; nunca é ecoado em lugar nenhum. Prefira o `diagnos login`: um token na linha de comando vai parar no `ps` e no histórico do shell |
| `--vault-url URL` | sobrescreve `DIAGNOS_VAULT_URL` nesta invocação |
| `--no-color` | sem nenhum escape ANSI — cores, negrito e esmaecido (a variável de ambiente `NO_COLOR` também) |
| `--version` | imprime a versão da CLI e sai |

Todo o resto — timeouts, precisão de datas, OpenBao — vem do ambiente, exatamente como no SDK
([Configuração](configuration.pt-BR.md)).

## Entrando

Cole o token da conta de serviço uma vez:

```sh
diagnos login
```

```text
Token (dgn_sk1_…):
Logged in · Sessão iniciada
  identity · identidade: svc_3f2a…@ws_….diagnos.health
  groups · grupos:       sg_oncology, sg_radiology
  stored in · guardado:  keyring (keyring.backends.macOS.Keyring)
```

O `login` lê o token com entrada oculta (colar funciona, e um pipe também), confere o CRC **antes de qualquer chamada
de rede** — um token cortado diz "truncado ou colado errado", não um 401 confuso — e então o prova: abre uma sessão, o
que só acontece quando o cofre verifica as assinaturas Ed25519 e ML-DSA-65. Só então ele é guardado:

1. no **chaveiro do sistema** quando há um que cifra em repouso — Keychain do macOS, Credential Locker do Windows,
   Secret Service ou KWallet no Linux. Um backend de chaveiro em texto puro ou "null" (como os backends de arquivo do
   `keyrings.alt`) conta como sem chaveiro;
2. senão no **OpenBao**, em `secret/diagnos/token`, quando `OPENBAO_ADDR` e um token do OpenBao estão definidos — o
   lugar de um servidor;
3. senão em lugar nenhum: o comando recusa e explica as duas opções.

Ele nunca grava o token num arquivo de texto. `--store keyring` ou `--store openbao` estreita a escolha a um lugar só.
Depois disso, todo comando acha o token sozinho:

```sh
diagnos whoami                   # qual token, de onde, e os grupos que o cofre deu a ele
diagnos patients list            # abre a própria sessão com uma requisição assinada
diagnos logout                   # remove o token do chaveiro (e do OpenBao, quando configurado)
```

O `whoami` prova o token contra o cofre e imprime a identidade, o workspace, de onde o token veio e os grupos da
sessão. O `status` informa a mesma identidade, o OpenBao, o enclave de memória e o agente de sessão sem tocar a rede;
o `status --check` também abre uma sessão e lista os grupos, e o `groups` os lista um por linha.

### `DIAGNOS_TOKEN` em CI e containers

Em CI e containers de vida curta não há chaveiro nem quem digite: ponha o token em `DIAGNOS_TOKEN`, direto do cofre de
segredos. Ele vence o que o `login` guardou. Quando o token veio do ambiente num terminal interativo, a CLI avisa uma
vez e recomenda o `diagnos login`.

```sh
DIAGNOS_TOKEN="$(cat /run/secrets/diagnos-token)" diagnos --quiet patients list --all
```

Nenhum comando pede nada a uma pessoa: toda invocação abre a própria sessão com uma requisição assinada, e abre outra
se o cofre a perder.

## O token legado no terminal

O token `apikey-` obsoleto (`DIAGNOS_API_TOKEN`, até 2027-04-15) ainda precisa de um enrollment aprovado antes de
decifrar qualquer coisa. O primeiro comando que precisa de um mostra um painel na `stderr` e espera:

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

Um admin abre o link, confere a máquina descrita ali, digita o código e escolhe os grupos. Para aprovar uma vez e
manter essa sessão para os comandos seguintes, rode `diagnos session start`:

```sh
diagnos session start            # aprova uma vez
diagnos patients list            # reaproveita a sessão
diagnos logout                   # encerra no cofre e apaga as chaves
```

**Como funciona.** O `session start` sobe um pequeno processo em segundo plano para o seu token, o *agente de
sessão*, e a sessão é destravada dentro dele, no enclave em Rust do SDK: RAM travada, fora de core dumps, apagada na
saída. Os comandos seguintes nunca recebem as chaves. Eles entregam os argumentos ao agente por um socket Unix
privado; o agente roda o comando ele mesmo e devolve a saída, os prompts e o código de saída. Então `--json`, pipes,
caminhos relativos como `-o out.dcm`, prompts de confirmação e códigos de saída se comportam exatamente como se o
comando rodasse no seu shell. Nada é gravado em disco.

- **Ele termina** no `diagnos logout`, depois de `DIAGNOS_AGENT_IDLE_MINUTES` sem comando (padrão `480`, 8 horas), ou
  num `SIGTERM` (um desligamento, digamos). Em todo caso, a sessão é revogada no cofre e as chaves apagadas. O
  `diagnos session lock` revoga a sessão mas mantém o agente: o próximo comando faz enrollment de novo.
- **Só você o usa.** O socket mora em `$XDG_RUNTIME_DIR/diagnos-<uid>/` (senão no diretório temporário), que precisa
  ser seu com modo `0700` — qualquer outra coisa é recusada, nunca consertada — e no Linux o agente também confere o
  uid do processo que conecta. Há um agente por token e URL do cofre.
- **Sem o `session start`**, ou com `DIAGNOS_AGENT=off`, cada comando roda no próprio processo e faz enrollment
  sozinho na primeira vez que precisa do cofre. O Windows ainda não tem agente e sempre funciona assim.

Para algo que roda sem ninguém olhando com o token legado, o
[auto-unseal com OpenBao](sessions.pt-BR.md#auto-unseal-com-openbao) salva a sessão depois da primeira aprovação
(`--no-auto-unseal` desliga isso num `session start`). Melhor: troque para o token de conta de serviço, que não precisa
de aprovação nenhuma ([MIGRATING.pt-BR.md](../../MIGRATING.pt-BR.md)).

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

Um registro vem de `--file` ou das flags inline, nunca dos dois — misturar é recusado, com o nome das flags.
`--file -` o lê do stdin, como em `jq '.patient' export.json | diagnos patients create --file -`.

**Para qual security group uma gravação vai.** `patients create`, `exams create`, `files upload` e `files mkdir`
selam sob `--group`, senão `DIAGNOS_GROUP`, senão — num exame — o grupo do paciente, senão o único grupo que esta
sessão tem (a CLI diz qual escolheu). Com vários grupos e nada disso, o comando para e lista as opções: nunca chuta,
porque selar sob o grupo errado entrega o registro à equipe errada.

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
| `login` | os campos do `whoami`, mais `stored_in` e `shadowed_by` (as variáveis que venceriam o token guardado) |
| `whoami` | `identity`, `key_id`, `workspace_id`, `token_kind`, `token_source`, `security_groups`, `session_expires_at` |
| `logout` | `{"removed_from": […], "agent_stopped": …, "diagnos_token_still_set": …}` |
| `groups` | `{"security_groups": […]}` |
| `status` | `workspace_id`, `key_id`, `identity`, `token_source`, `openbao_configured`, `sdk_version`, `memory`, `agent` — e `security_groups` com `--check` |

```sh
diagnos --json patients list --all | jq -r '.items[].index.document_id'
diagnos --json exams list --all | jq -r '.items[] | select(.index.meta.patient_id == "PATIENT_ID") | .index.document_id'
diagnos --json files list --exam EXAM_ID --all | jq -r '.items[] | "\(.node.node_id)\t\(.name)"'
```

Erros nunca vão para o `stdout`: vão para o `stderr` numa linha, e o código de saída diz o que aconteceu.

### Códigos de saída

`0` é sucesso; `2` um problema de configuração (nenhum token achado, um token colado errado, nenhum lugar seguro para
guardá-lo); `3` autenticação, permissão, sessão ou enrollment; `4` não encontrado;
`5` cota; `6` limite de taxa; `7` conflito; `1` qualquer outra coisa, um problema de arquivo local inclusive. O
mapeamento completo de cada exceção do SDK está em [Erros](errors.pt-BR.md#toda-exceção).

### Tarefas sem ninguém olhando

```sh
#!/bin/sh
# nightly-upload.sh — rodado pelo cron; o token está no OpenBao (OPENBAO_ADDR, OPENBAO_TOKEN_FILE) ou no DIAGNOS_TOKEN
set -eu
diagnos --quiet --no-color files upload --group sg_radiology --exam "$EXAM_ID" /data/outbox/*.dcm
```

Use `--quiet` para nenhum spinner escrever no log, e o código de saída — não o texto — para decidir o que aconteceu.
Com o token de conta de serviço nenhuma execução espera uma pessoa.
