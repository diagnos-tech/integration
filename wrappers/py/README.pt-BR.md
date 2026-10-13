# diagnos

**O cofre diagnos no Python — SDK zero-knowledge, linha de comando e API REST, num pacote só.**

[English](README.md) · **Português (Brasil)**

[![PyPI](https://img.shields.io/pypi/v/diagnos?color=3776ab)](https://pypi.org/project/diagnos/)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab)](https://pypi.org/project/diagnos/)
[![Licença: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-64748b)](https://github.com/diagnos-tech/integration/blob/develop/LICENSE)

Tudo que é clínico é cifrado **dentro do seu processo** antes de tocar a rede — o cofre só vê texto cifrado. Um
pacote traz todas as portas de entrada; você instala só as camadas que usa.

## Instale o que você precisa

| Você quer | Instale | Você ganha |
|---|---|---|
| Uma primeira olhada | `pip install diagnos` | `diagnos docs`, `version`, `setup`, `help` — sem dependência nenhuma |
| O SDK, no seu código | `pip install "diagnos[sdk]"` | `from diagnos import Diagnos` |
| A linha de comando | `pip install "diagnos[cli]"` | `diagnos login`, `diagnos patients list`, … |
| A API REST | `pip install "diagnos[api]"` | `diagnos-api` — FastAPI com mTLS obrigatório |

Os extras se combinam (`"diagnos[cli,api]"`). Mais dois ficam por cima: `openbao` (auto-unseal com OpenBao para
servidores) e `dev-certs` (`diagnos-api dev-certs`, certificados locais). Com o [uv](https://docs.astral.sh/uv/):
`uv add "diagnos[sdk]"` num projeto, `uv tool install "diagnos[cli]"` para a linha de comando. A API REST também sai
como imagem de container assinada: `ghcr.io/diagnos-tech/diagnos-api`.

Python 3.11 a 3.13, no Linux (glibc e musl, x86_64 e arm64), macOS (Apple silicon e Intel) e Windows (x86_64). Todo
wheel traz o enclave de memória em Rust pré-compilado — nenhum compilador necessário.

## Deixe o `diagnos` configurar

A instalação base sabe instalar o resto, passo a passo:

```sh
uv tool install diagnos   # ou: pipx install diagnos
diagnos setup sdk         # soma o SDK ao projeto Python desta pasta (uv)
diagnos setup cli         # dá a este `diagnos` todos os comandos (uv)
diagnos setup api         # baixa a imagem da API e verifica a assinatura (Docker, cosign)
```

Todo comando é mostrado antes de rodar e confirmado uma vez. `--dry-run` só imprime o plano; `--yes` roda sem
perguntar, para scripts. Uma ferramenta ausente (`uv`, Docker) nunca é instalada por você: o `setup` diz onde
obtê-la e sai com `69`.

## Os comandos da base

| Comando | Faz |
|---|---|
| `diagnos docs [help\|dev\|trust] [--open] [--json]` | Lista a Central de Ajuda, a Developer Central e o Trust Center, ou imprime (ou abre) um |
| `diagnos version [--json]` | Esta instalação: versão, interpretador, plataforma e quais extras estão dentro |
| `diagnos setup sdk\|cli\|api [--yes] [--dry-run]` | Instala uma camada, passo a passo |
| `diagnos help [comando]` | A visão geral, ou as opções de um comando |

Com o `diagnos[cli]` instalado, o `diagnos` é a linha de comando completa e continua respondendo estes quatro.
Códigos de saída: `0` sucesso, `1` um passo falhou ou foi recusado, `2` erro de uso, `69` falta algo de que isto
precisa.

## Início rápido

```python
from diagnos import Diagnos

with Diagnos() as vault:  # faz enrollment na entrada: imprime o link de aprovação + código
    print(vault.security_groups)
```

Defina o `DIAGNOS_API_TOKEN` antes — um admin do workspace o emite no app web do diagnos. O
[início rápido](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/quickstart.pt-BR.md) vai daqui
até o seu primeiro paciente e arquivo cifrados.

## Verifique o que você instala

Todo release é construído por um único workflow do GitHub Actions e assinado lá, sem chave, com o
[Sigstore](https://www.sigstore.dev/). O PyPI mostra a proveniência de cada arquivo; os mesmos arquivos, os bundles
`.sigstore.json` deles e o `SHA256SUMS` vão anexados ao
[release no GitHub](https://github.com/diagnos-tech/integration/releases). Com o `cosign`:

```sh
cosign verify-blob diagnos-0.1.0.tar.gz \
  --bundle diagnos-0.1.0.tar.gz.sigstore.json \
  --certificate-identity "https://github.com/diagnos-tech/integration/.github/workflows/release.yml@refs/tags/v0.1.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"

cosign verify ghcr.io/diagnos-tech/diagnos-api:0.1.0 \
  --certificate-identity "https://github.com/diagnos-tech/integration/.github/workflows/release.yml@refs/tags/v0.1.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

Ou com o GitHub CLI: `gh attestation verify diagnos-0.1.0.tar.gz --repo diagnos-tech/integration`.

## Saiba mais

- **Central de Ajuda** — <https://docs.diagnos.health>
- **Developer Central** — <https://dev.diagnos.health>
- **Trust Center** — <https://trust.diagnos.health>
- **Código, issues e changelog** — <https://github.com/diagnos-tech/integration>

Licenciado sob [Apache-2.0](https://github.com/diagnos-tech/integration/blob/develop/LICENSE). Reporte uma
vulnerabilidade em privado pelo [GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new).
