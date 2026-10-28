# diagnos

**O cofre diagnos a partir do Node.js — ache a documentação e configure o SDK, a CLI e a API REST de conhecimento zero, passo a passo.**

[English](README.md) · **Português (Brasil)**

[![npm](https://img.shields.io/npm/v/diagnos?color=cb3837)](https://www.npmjs.com/package/diagnos)
[![Node.js ≥ 22](https://img.shields.io/badge/node-%E2%89%A5%2022-417e38)](https://nodejs.org/)
[![Licença: Apache-2.0](https://img.shields.io/badge/licen%C3%A7a-Apache--2.0-64748b)](https://github.com/diagnos-tech/integration/blob/main/LICENSE)

O diagnos cifra tudo que é clínico **dentro do seu processo** antes de tocar a rede — o cofre só vê texto cifrado.
O SDK, a linha de comando e a API REST são escritos em Python e saem num pacote só,
[`diagnos` no PyPI](https://pypi.org/project/diagnos/), mais uma imagem de container assinada. Este pacote é a porta
de entrada para quem programa em Node.js: sem dependências, nada roda na instalação, e ele faz exatamente quatro
coisas — as mesmas quatro, do mesmo jeito, que o `pip install diagnos`.

```sh
npx diagnos                 # o que há aqui
npx diagnos docs dev        # https://dev.diagnos.health
npx diagnos setup api       # baixa a imagem da API REST e verifica a assinatura
```

## Comandos

| Comando | Faz |
|---|---|
| `diagnos docs [help\|dev\|trust] [--open] [--json]` | Lista a Central de Ajuda, a Developer Central e o Trust Center; com um tópico, imprime só aquela URL (ou a abre) |
| `diagnos version [--json]` | A versão deste wrapper, o runtime e a plataforma dele, e quais camadas Python estão instaladas |
| `diagnos setup sdk\|cli\|api [--yes] [--dry-run]` | Instala uma camada: o SDK e a CLI com `uv`, a API como imagem assinada com Docker |
| `diagnos help [comando]` | A visão geral, ou as opções de um comando |

Todo outro comando — `diagnos login`, `diagnos patients list`, … — pertence à linha de comando completa. Depois que o
`diagnos setup cli` a instala, este `diagnos` lhe entrega esses comandos intactos, então um `diagnos` só responde a
tudo, seja qual for o primeiro no seu `PATH`.

## O que o `setup` instala

| Alvo | Precisa de | Roda |
|---|---|---|
| `sdk` | [uv](https://docs.astral.sh/uv/) | `uv add "diagnos[sdk]>=<versão>"` no projeto Python em volta de você, `uv pip install` no ambiente virtual ativo, ou `uv init` + `uv add` aqui mesmo |
| `cli` | uv | `uv tool install "diagnos[cli]==<versão>"` — ou, se já há um `diagnos` Python instalado, ele soma a própria CLI onde mora |
| `api` | [Docker](https://docs.docker.com/get-started/get-docker/), e opcionalmente [cosign](https://docs.sigstore.dev/cosign/system_config/installation/) ≥ 3.1.3 | `docker pull ghcr.io/diagnos-tech/diagnos-api:<versão>`, depois `cosign verify` do digest baixado, depois imprime um `docker run` endurecido por esse digest |

`<versão>` é a versão deste próprio pacote: o `diagnos@0.1.0` do npm configura o `diagnos==0.1.0` do PyPI e a
imagem `0.1.0`. Eles saem juntos.

## Seguro por construção

- **Mostra antes de rodar.** Todo comando que o `setup` vai rodar é impresso antes e confirmado uma vez, com *não*
  como padrão. `--yes` pula a pergunta, `--dry-run` não roda nada. Sem terminal e sem `--yes`, nada roda.
- **Nunca instala uma ferramenta.** Um `uv` ou Docker ausente termina com a página oficial de instalação e o código
  de saída `69` — nunca um instalador baixado, nunca `curl | sh`.
- **Sem shell, sem surpresas no `PATH`.** Programas rodam de uma lista de argumentos, resolvidos uma vez para um
  caminho absoluto; entradas relativas do `PATH` são ignoradas, e no Windows só arquivos `.exe` rodam.
- **Verifica o que baixa.** A imagem da API é verificada *pelo digest que o Docker baixou*, contra um assinante só: o
  `release.yml` do repositório integration, rodado pelo push da tag desta versão, pelo emissor OIDC do GitHub. Uma
  imagem cuja assinatura falha é removida na hora. Sem cosign, ele diz *NÃO verificada*, bem alto.
- **Escapa o que não escreveu.** Caminhos e outro texto de fora são impressos com caracteres de controle escapados,
  para nada recolorir ou reescrever o plano que você aprova.
- **Nada em segundo plano.** Sem scripts de instalação, sem telemetria, sem acesso próprio à rede: os únicos
  programas com que ele fala são os que ele mostra a você.

## Para scripts

`--json` imprime os mesmos formatos da base Python. `diagnos docs --json`:

```json
{
  "help": { "name": "Help Center", "url": "https://docs.diagnos.health" },
  "dev": { "name": "Developer Central", "url": "https://dev.diagnos.health" },
  "trust": { "name": "Trust Center", "url": "https://trust.diagnos.health" }
}
```

`diagnos version --json` traz `diagnos`, `node`, `implementation`, `executable`, `platform`, `extras` (o
`{extra: instalado}` da própria base Python, vazio quando não há nenhuma) e `layers` (qual `diagnos` Python
respondeu, ou `null`). A saída em texto é bilíngue (`English · Português`) e respeita o `NO_COLOR`.

| Código de saída | Significado |
|---|---|
| `0` | Sucesso |
| `1` | Um passo falhou, ou a confirmação foi negada |
| `2` | Erro de uso (inclusive "sem terminal para confirmar") |
| `69` | Algo de que isto precisa — `uv`, Docker — não está instalado |

A mesma linha de comando pode ser importada: `import { main } from "diagnos"; process.exitCode = await main(["docs", "--json"]);`.

## Saiba mais

- **Central de Ajuda** — <https://docs.diagnos.health>
- **Developer Central** — <https://dev.diagnos.health>
- **Trust Center** — <https://trust.diagnos.health>
- **Código, issues e changelog** — <https://github.com/diagnos-tech/integration> (este pacote mora em
  `wrappers/ts`, e implementa o [`wrappers/contract.json`](https://github.com/diagnos-tech/integration/blob/develop/wrappers/contract.json))

Licenciado sob [Apache-2.0](https://github.com/diagnos-tech/integration/blob/main/LICENSE). Relate uma
vulnerabilidade em privado pelo [GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new).
