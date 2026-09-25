# diagnos-cli

🇺🇸 The `diagnos` command line — the zero-knowledge diagnos vault, from your
terminal, built on top of the [`diagnos`](../sdk/README.md) SDK. Every byte
of cryptography, signing and retry logic lives in the SDK; this package only
parses arguments and renders what the SDK returns.
🇧🇷 A linha de comando `diagnos` — o cofre zero-knowledge diagnos, do seu
terminal, construída em cima do SDK [`diagnos`](../sdk/README.md). Todo byte
de criptografia, assinatura e retentativa mora no SDK; este pacote só
interpreta argumentos e renderiza o que o SDK devolve.

## Install · Instalação

```sh
pipx install diagnos-cli
export DIAGNOS_API_TOKEN="apikey-…"   # 🇺🇸 issued by a workspace admin · 🇧🇷 emitido por um admin do workspace
```

🇺🇸 `DIAGNOS_API_TOKEN` identifies *this* service account and its workspace;
it does not, by itself, unlock anything — that is what `diagnos login` is
for. `--token` on any command overrides it for that one invocation, and is
never echoed anywhere (not in `--help`, not in output, not in `--json`).
🇧🇷 `DIAGNOS_API_TOKEN` identifica *esta* service account e o workspace dela;
sozinho, ele não desbloqueia nada — é para isso que serve `diagnos login`.
`--token` em qualquer comando o sobrescreve só para aquela invocação, e nunca
é ecoado em lugar nenhum (nem no `--help`, nem na saída, nem no `--json`).

## Your first `diagnos login` · Seu primeiro `diagnos login`

```sh
$ diagnos login
```

🇺🇸 The first time an `diagnos` process runs (and every time after, unless
OpenBao is configured — see below), it has to *enroll*. `login` runs that
dance explicitly, so you can watch it happen: a panel with a link and a
6-digit code appears, then a spinner while it waits.

```
╭─ diagnos · enrollment ─────────────────────────────╮
│ Open this link and type the code below to approve  │
│ this session.                                      │
│ Abra este link e digite o código abaixo para        │
│ aprovar esta sessão.                                │
│                                                      │
│ https://vault.diagnos.health/enroll/…                  │
│                                                      │
│   1  2  3  4  5  6                                  │
╰──────────────────────────────────────────────────────╯
⠋ waiting for approval… · aguardando aprovação…
```

🇺🇸 Open that link, type the code, and pick which security groups this CLI
process may read. Once a workspace admin approves, `login` prints what was
granted:

```
Enrolled · Sessão estabelecida
  workspace_id: ws_...
  account_id:   acct_...
  groups · grupos: sg_oncology, sg_radiology
```

**The CLI never persists the session to disk.** Without OpenBao configured
(next section), that session lives only in this process's memory — the
moment it exits, it is gone, and the *next* `diagnos` invocation enrolls
again, from scratch, with a brand new link and code. This is not a bug to
route around: `login` on its own is for *validating a token and seeing what
it was granted*, one process at a time. Every other command (`patients`,
`exams`, `files`, `groups`) also enrolls lazily on its own if no session is
available — you do not have to run `login` first.

🇧🇷 Na primeira vez que um processo `diagnos` roda (e em toda vez depois, a
menos que o OpenBao esteja configurado — veja abaixo), ele precisa fazer
*enrollment*. `login` roda essa dança de forma explícita, para você ver
acontecer: aparece um painel com um link e um código de 6 dígitos, depois um
spinner enquanto espera.

Abra o link, digite o código, e escolha quais security groups este processo
da CLI pode ler. Assim que um admin do workspace aprova, `login` imprime o
que foi concedido (exemplo acima).

**A CLI nunca guarda a sessão em disco.** Sem o OpenBao configurado (próxima
seção), essa sessão vive só na memória deste processo — no instante em que
ele termina, ela some, e a *próxima* invocação de `diagnos` faz enrollment
de novo, do zero, com link e código novos. Isto não é um bug para contornar:
`login` sozinho serve para *validar um token e ver o que foi concedido*, um
processo por vez. Todo outro comando (`patients`, `exams`, `files`,
`groups`) também faz enrollment sozinho, de forma preguiçosa, se não houver
sessão disponível — você não precisa rodar `login` antes.

## OpenBao, for servers · OpenBao, para servidores

🇺🇸 A human approval on every restart is fine for a one-off script; it is not
fine for a cron job or a Kubernetes pod. Set `OPENBAO_ADDR`/`OPENBAO_TOKEN`
(see the [SDK's README](../sdk/README.md#auto-unseal-with-openbao--auto-unseal-com-openbao)
for the full tradeoff) and every command's `unlock()` saves the session to
OpenBao's encrypted KV store after a successful enrollment, and restores
from there on the next invocation — no human, no new link, until the saved
session itself expires. `login --auto-unseal`/`--no-auto-unseal` overrides
the automatic default (on iff `OPENBAO_ADDR` is set) for one invocation.

🇧🇷 Uma aprovação humana a cada reinício é aceitável num script avulso; não é
aceitável num cron job ou num pod Kubernetes. Configure
`OPENBAO_ADDR`/`OPENBAO_TOKEN` (veja o
[README do SDK](../sdk/README.md#auto-unseal-with-openbao--auto-unseal-com-openbao)
para o tradeoff completo) e o `unlock()` de todo comando salva a sessão no
KV cifrado do OpenBao depois de um enrollment bem-sucedido, e restaura de lá
na próxima invocação — sem humano, sem link novo, até a sessão salva em si
expirar. `login --auto-unseal`/`--no-auto-unseal` sobrescreve o padrão
automático (ligado se `OPENBAO_ADDR` estiver definida) só para aquela
invocação.

## Commands · Comandos

| Command · Comando | 🇺🇸 · 🇧🇷 |
|---|---|
| `diagnos login [--auto-unseal/--no-auto-unseal]` | Enrolls, shows what was granted. · Faz enrollment, mostra o que foi concedido. |
| `diagnos status [--check]` | Parsed token, OpenBao, SDK version; `--check` also unlocks. · Token interpretado, OpenBao, versão do SDK; `--check` também desbloqueia. |
| `diagnos groups` | Lists granted security groups. · Lista os security groups concedidos. |
| `diagnos patients list [--group G] [--include-deleted] [--limit N] [--cursor C] [--all]` | Pages patient indexes. · Pagina índices de paciente. |
| `diagnos patients get ID [--version V]` | Decrypts and shows one patient. · Decifra e mostra um paciente. |
| `diagnos patients create --group G (--file record.json \| --legal-name ... --display-name ...)` | Creates a patient. · Cria um paciente. |
| `diagnos patients update ID --file record.json` | New version of the record. · Versão nova do registro. |
| `diagnos patients archive\|unarchive\|delete ID [--yes]` | Flips a flag in a new version (`delete` asks first). · Vira uma flag numa versão nova (`delete` confirma antes). |
| `diagnos exams list\|get\|create\|update\|archive\|unarchive\|delete` | Same shape as `patients`, plus `--patient`/`--modality`. · Mesma forma de `patients`, mais `--patient`/`--modality`. |
| `diagnos files list --group G [--exam E] [--include-pending] [--all]` | Lists drive nodes, name decrypted. · Lista nós de drive, nome decifrado. |
| `diagnos files upload --group G PATH... [--exam E]` | Uploads one batch. · Sobe um lote. |
| `diagnos files download --group G NODE_ID [-o DEST]` | Downloads and decrypts. · Baixa e decifra. |
| `diagnos files get --group G NODE_ID` | One node's metadata. · Metadado de um nó. |
| `diagnos session lock` | Ends the session, best-effort. · Encerra a sessão, best-effort. |

🇺🇸 Global options on the root command, before the subcommand:
🇧🇷 Opções globais no comando raiz, antes do subcomando:

| Option · Opção | 🇺🇸 · 🇧🇷 |
|---|---|
| `--json` | Machine-readable output, no tables/panels/spinners. · Saída para máquina, sem tabelas/painéis/spinners. |
| `--quiet` / `-q` | Suppresses spinners and progress bars. · Suprime spinners e barras de progresso. |
| `--vault-url URL` | Overrides `DIAGNOS_VAULT_URL`. · Sobrescreve `DIAGNOS_VAULT_URL`. |
| `--token TOKEN` | Overrides `DIAGNOS_API_TOKEN`; never echoed. · Sobrescreve `DIAGNOS_API_TOKEN`; nunca ecoado. |
| `--no-color` | Disables ANSI colors. · Desliga cores ANSI. |
| `--version` | Prints the CLI version and exits. · Imprime a versão da CLI e sai. |

## `--json`, for scripts · `--json`, para scripts

🇺🇸 Every command accepts `--json` before the subcommand name — the output is
plain `json.dumps`, never wrapped by `rich`, so a long field can never break
a line mid-document the way a terminal-width-aware renderer could:

🇧🇷 Todo comando aceita `--json` antes do nome do subcomando — a saída é
`json.dumps` puro, nunca envolvida por `rich`, então um campo longo nunca
quebra uma linha no meio do documento do jeito que um renderizador ciente da
largura do terminal poderia:

```sh
diagnos --json patients list --group sg_oncology | jq '.items[].document_id'
```

## Exit codes · Códigos de saída

🇺🇸 Stable and documented, for `if`/`case` in a script — never grep the error
text:
🇧🇷 Estáveis e documentados, para `if`/`case` num script — nunca faça grep do
texto do erro:

| Code · Código | Meaning · Significado |
|---|---|
| `0` | Success · Sucesso |
| `1` | Other error (includes invalid input, e.g. `ValidationError`). · Outro erro (inclui entrada inválida, ex.: `ValidationError`). |
| `2` | Configuration error (missing/malformed token, env var). · Erro de configuração (token ausente/malformado, variável de ambiente). |
| `3` | Authentication/permission/session (`AuthenticationError`, `DiagnosPermissionError`, `SessionExpiredError`, enrollment denied/expired). · Autenticação/permissão/sessão. |
| `4` | Not found. · Não encontrado. |
| `5` | Quota exceeded. · Cota excedida. |
| `6` | Rate limited. · Limite de taxa. |
| `7` | Conflict (pending version, replay). · Conflito (versão pendente, replay). |

## Development · Desenvolvimento

```sh
uv sync --all-packages
uv run --package diagnos-cli pytest cli/tests -q
uv run ruff check cli && uv run ruff format --check cli
uv run mypy cli/src
```

🇺🇸 See `../CONVENTIONS.md` for the bilingual-docstring rule and the "`cli`
imports only `diagnos`" boundary, and `../README.md` for the workspace
layout.
🇧🇷 Veja `../CONVENTIONS.md` para a regra de docstring bilíngue e a fronteira
"`cli` importa só `diagnos`", e `../README.md` para a estrutura do
workspace.
