# Wrappers

[English](README.md) · **Português (Brasil)**

A integração diagnos é escrita em Python — o SDK, a linha de comando e a API REST saem num pacote só,
[`diagnos`](py/README.pt-BR.md). Um *wrapper* é o programa pequeno e sem dependências que quem desenvolve encontra
primeiro, na linguagem que já usa: explica onde as coisas estão e instala o resto. Todo wrapper faz exatamente
quatro coisas, do mesmo jeito, para os primeiros cinco minutos serem iguais começando pelo `pip`, pelo `npm` ou pelo
`go`.

| Wrapper | Pacote | Situação |
|---|---|---|
| [`py/`](py/README.pt-BR.md) | `pip install diagnos` — a base do próprio pacote Python (`src/diagnos/_wrapper`) | ✅ |
| [`ts/`](ts/README.pt-BR.md) | `npx diagnos` — TypeScript para Node.js, no npm como [`diagnos`](https://www.npmjs.com/package/diagnos); configura as camadas Python, quase sempre o container da API | ✅ |
| `go/`, … | `go run …` | planejado |

## O contrato

O [`contract.json`](contract.json) é a fonte da verdade legível por máquina: comandos, opções, links, alvos do
`setup` e códigos de saída. Um wrapper traz um teste de conformidade contra ele — o do Python é o
[`py/tests/test_contract.py`](py/tests/test_contract.py), o do TypeScript é o
[`ts/test/contract.test.ts`](ts/test/contract.test.ts).

| Comando | Faz |
|---|---|
| `diagnos docs [help\|dev\|trust] [--open] [--json]` | Lista a Central de Ajuda, a Developer Central e o Trust Center; com um tópico, imprime só aquela URL (ou a abre) |
| `diagnos version [--json]` | A versão do wrapper, o runtime e a plataforma dele, e quais camadas Python estão instaladas |
| `diagnos setup sdk\|cli\|api [--yes] [--dry-run]` | Instala uma camada: o SDK e a CLI com `uv`, a API como imagem assinada com Docker |
| `diagnos help [comando]` | A visão geral, ou as opções de um comando |

Regras que todo wrapper mantém:

- **Mostra antes de rodar.** Todo comando que o `setup` vai rodar é impresso antes e confirmado uma vez, com *não*
  como padrão; `--yes` pula a pergunta, `--dry-run` não roda nada. Sem terminal e sem `--yes`, nada roda e o código
  de saída é `2`.
- **Nunca instala uma ferramenta.** Um `uv` ou Docker ausente termina com a página oficial de instalação e o código
  de saída `69` — nunca um instalador baixado, nunca `curl | sh`.
- **Sem shell, sem surpresas no `PATH`.** Programas rodam de uma lista argv, resolvidos uma vez para um caminho
  absoluto; entradas relativas do `PATH` são ignoradas.
- **Verifica o que baixa.** O `setup api` lê o digest que o Docker baixou, verifica esse digest com o `cosign`
  (≥ 3.1.3) contra o `signer` do contrato — o workflow de release na tag desta versão, rodado por um `push` — e
  imprime o `docker run` pelo digest. Sem cosign ele diz *NÃO verificada*, em alto e bom som.
- **Escapa o que não escreveu.** Caminhos e outros textos de fora saem com os caracteres de controle escapados, para
  nada recolorir nem reescrever o plano que a pessoa aprova; toda versão que ele escreve num comando é fixada.
- **Mesma saída.** O `--json` imprime exatamente os formatos que a base Python imprime; a saída de texto é bilíngue
  (`English · Português`) e respeita o `NO_COLOR`.

| Código de saída | Significado |
|---|---|
| `0` | Sucesso |
| `1` | Um passo falhou, ou a confirmação foi recusada |
| `2` | Erro de uso (inclusive "sem terminal para confirmar") |
| `69` | Falta algo de que isto precisa — `uv`, Docker, um extra |
