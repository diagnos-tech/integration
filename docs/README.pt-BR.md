# Documentação

[English](README.md) · **Português (Brasil)**

Este repositório é a fonte única da documentação para desenvolvedores do diagnos. O site a publica em `/dev/docs`,
lendo este repositório num commit fixado; o GitHub renderiza exatamente os mesmos arquivos. Esta página é para quem
escreve ou muda a doc: onde tudo mora, as regras que toda página segue, e o que o `make docs-check` prova antes de uma
mudança poder entrar.

## Estrutura

```text
README.md                     a página de visão geral (a raiz do site)
apps/sdk/README.md            páginas iniciais dos pacotes — também as descrições do PyPI
apps/cli/README.md
apps/api/README.md
apps/api/deploy/**/README.md  implantação: Docker Compose, Kubernetes, auto-unseal do OpenBao
docs/
├── README.md                 esta página
├── site.json                 navegação, ids de página e descrições de SEO — escrito à mão
├── guides/                   início rápido, conceitos, sessões, pacientes, … — os guias escritos à mão
├── reference/                openapi.json, cli.json, sdk.json — GERADOS a partir do código, nunca editados
├── PROTOCOL.md               o contrato de fio normativo
└── COMPATIBILITY.md          o que funciona contra o cofre de hoje
scripts/docs/                 os geradores e as checagens por trás de `make docs` e `make docs-check`
```

## Escrevendo uma página

- **Dois arquivos, uma página.** Toda página é `NOME.md` (inglês) ao lado de `NOME.pt-BR.md` (português do Brasil),
  com um seletor de idioma logo abaixo do H1. Os dois precisam ter o mesmo esqueleto — os mesmos níveis de título e os
  mesmos blocos de código, na mesma ordem — e o `make docs-check` os compara.
- **O primeiro `# H1` é o título.** Sem frontmatter YAML: o GitHub o renderizaria como uma tabela no topo da página. O
  que o site precisa além do Markdown mora no [`site.json`](site.json).
- **Cada fato mora num lugar só.** Explique uma coisa uma vez e aponte para ela; os READMEs dos pacotes são páginas
  iniciais que apontam para os guias, não cópias deles. Comandos, rotas e classes estão na referência gerada, nunca
  digitados à mão numa tabela.
- **Links são relativos** (`[Sessões](guides/sessions.pt-BR.md#auto-unseal-com-openbao)`): o site transforma um link
  para uma página do manifesto num link para essa página, e qualquer outro num link para o GitHub no commit fixado. Os
  READMEs dos pacotes apontam para arquivos fora do pacote com URLs absolutas do GitHub, porque o PyPI não resolve
  links relativos. Para apontar para uma seção de referência, faça link para o JSON dela (`reference/sdk.json`).
- **Alertas e diagramas**: `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]` e `> [!CAUTION]` viram callouts,
  e blocos ```` ```mermaid ```` viram diagramas — no GitHub e no site. Use onde esclarecem, não para enfeitar.
- **A voz** é a do repositório: direta, precisa, e sempre dizendo *por quê* — a ameaça, o custo, a regra do protocolo.
  O [CONTRIBUTING.pt-BR.md](../CONTRIBUTING.pt-BR.md) tem o resto das convenções.

### Acrescentando uma página ao site

Um arquivo Markdown só é publicado quando o `site.json` o lista, dentro de um grupo de navegação:

```json
{
  "id": "sdk/patients",
  "source": "docs/guides/patients.md",
  "description": {
    "en": "Create, read, update, archive and delete encrypted patient records with the diagnos SDK…",
    "pt-br": "Crie, leia, atualize, arquive e apague registros de paciente cifrados com o SDK diagnos…"
  }
}
```

- `id` é a URL da página (`/<lang>/dev/docs/<id>/`): letras minúsculas, dígitos e `-`, em segmentos separados por
  `/`, único no manifesto. `overview` é a página raiz e é obrigatória.
- `source` é o arquivo em inglês; o gêmeo `.pt-BR.md` é a página em português.
- `description` é copy para buscadores — no máximo 160 caracteres em cada língua — não prosa da página.
- `title` é só para um arquivo cujo H1 não serve de título de menu (o cabeçalho HTML centralizado do README raiz).
- Renomear um `id` quebra todo link para ele: acrescente `{"from": "id/antigo", "to": "id/novo"}` em `redirects`.
- Uma página com `"reference": "openapi" | "cli" | "sdk"` no lugar de `source` é uma seção gerada; o site a expande
  numa página por rota, comando ou classe.

## Exemplos executáveis

Todo bloco ```` ```python ```` de toda página do `site.json` — nas duas línguas — roda na CI. Essa é a convenção, e o
motivo de um exemplo daqui ser confiável:

- Os blocos de uma página rodam de cima para baixo, **num namespace só**, como um notebook: um bloco posterior pode
  usar `vault` ou `patient` de um anterior. Cada página começa de um sandbox novo.
- ```` ```python no-run ```` tira um bloco — um fragmento, uma assinatura, ou código que precisa de um OpenBao de
  verdade ou de uma API rodando. Qualquer outra linguagem nunca roda.
- **O sandbox é o SDK de verdade contra um cofre em memória.** `Diagnos()` lê um token de sandbox, faz enrollment com
  um par de chaves híbrido de verdade, assina toda requisição e sela todo registro e arquivo no enclave Rust; só a rede
  é trocada, pelo duplo de teste do próprio SDK para o cofre e o armazenamento de objetos
  (`apps/sdk/tests/resources/vault_double.py`). Todo enrollment é aprovado na hora com os grupos `sg_oncology` e
  `sg_radiology`, e o diretório de trabalho tem `scans/IM-0001.dcm`, `scans/IM-0002.dcm`, `photo.jpg` e `report.pdf`.
- A saída é capturada, e só aparece quando um bloco falha, na linha do Markdown que lançou.

Blocos de shell não rodam, mas toda linha `diagnos …` neles é interpretada contra a CLI: um comando ou uma flag
desconhecidos reprovam a checagem.

## Páginas de referência

Os três arquivos em `docs/reference/` são gerados a partir do código pelo `make docs`, e commitados. Para mudar o que
a referência diz, mude o código:

| Arquivo | Gerado a partir de | O texto vem de |
|---|---|---|
| `openapi.json` | o app FastAPI, `app.openapi()` | `summary`/`description` das rotas e descrições de parâmetro, escritos `🇺🇸 … 🇧🇷 …` |
| `cli.json` | a árvore de comandos `typer` do `diagnos` | textos `help=` escritos `English · Português`; exemplos do epílogo de cada comando (`diagnos_cli.examples`) |
| `sdk.json` | `diagnos.__all__`, lido com `inspect` | docstrings, com os parágrafos 🇺🇸/🇧🇷; campos documentados por uma string literal logo abaixo deles |

A divisão 🇺🇸/🇧🇷 segue uma regra só, compartilhada com o site (`scripts/docs/bilingual.py`): do 🇺🇸 até o 🇧🇷 é
inglês, do 🇧🇷 em diante é português; texto sem marcadores é publicado sem tradução, o que a checagem recusa.
`generatedFrom.commit` registra o commit sobre o qual uma referência foi regerada pela última vez; ele só muda quando o
conteúdo muda.

## As checagens

```sh
make docs         # regera docs/reference/*.json
make docs-check   # tudo abaixo; parte do `make check`, então a CI roda em todo pull request
```

O `make docs-check` falha quando:

- um arquivo gerado difere do que o `make docs` gravaria;
- o `site.json` quebra o contrato — um id fora da gramática ou repetido, um source ou gêmeo `.pt-BR.md` ausente, uma
  descrição com mais de 160 caracteres ou sem uma das línguas;
- uma página e o gêmeo não têm o mesmo esqueleto;
- um link relativo, uma âncora, ou um link absoluto para este repositório não resolve;
- um exemplo executável falha, ou uma linha `diagnos …` usa comando ou flag que não existe;
- o `diagnos … --help` diverge do `cli.json`, em qualquer sentido;
- algum texto gerado está sem tradução.

O `make lint`, à parte, confere que *todo* arquivo Markdown do repositório tem o gêmeo, o seletor de idioma e nenhum
link relativo morto (`scripts/check_docs.py`).
