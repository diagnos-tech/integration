[![diagnos](https://diagnos.health/brand/svg/diagnos-lockup-gradient.svg)](https://diagnos.health)

# integration

**SDK, CLI e API REST zero-knowledge para o cofre diagnos.**

[English](README.md) · **Português (Brasil)**

[![CI](https://github.com/diagnos-tech/integration/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/diagnos-tech/integration/actions/workflows/ci.yml?query=branch%3Amain)
[![Cobertura](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdiagnos-tech%2Fintegration%2Fbadges%2Fcoverage.json)](https://github.com/diagnos-tech/integration/actions/workflows/ci.yml?query=branch%3Amain)
[![Pacote](https://github.com/diagnos-tech/integration/actions/workflows/package.yml/badge.svg)](https://github.com/diagnos-tech/integration/actions/workflows/package.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/diagnos-tech/integration/badge)](https://scorecard.dev/viewer/?uri=github.com/diagnos-tech/integration)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab)](pyproject.toml)
[![Licença: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-64748b)](LICENSE)

**[Instalação](docs/guides/install.pt-BR.md)** · **[SDK](apps/sdk/README.pt-BR.md)** · **[CLI](apps/cli/README.pt-BR.md)** ·
**[API](apps/api/README.pt-BR.md)** · [Wrappers](wrappers/README.pt-BR.md) · [Protocolo](docs/PROTOCOL.pt-BR.md) ·
[Testes de contrato](contracts/README.pt-BR.md) · [Como contribuir](CONTRIBUTING.pt-BR.md) · [Segurança](SECURITY.pt-BR.md)

Um pacote Python de código aberto, `diagnos`, para falar com o cofre diagnos sem nunca lidar com URL assinada, HMAC ou
envelope de chave. Tudo que é clínico é cifrado **dentro do seu processo** antes de tocar a rede — o cofre só vê
ciphertext. Este pacote faz disso o caminho *fácil*.

> [!NOTE]
> **Situação: prévia 0.2.0.** Toda superfície — o token de conta de serviço, sessões, assinatura de requisições,
> pacientes, exames, arquivos e pastas — fala o protocolo atual do cofre e é verificada contra ele pelos
> [testes de contrato](contracts/README.pt-BR.md). Limites conhecidos, e as questões ainda em aberto do lado do cofre,
> estão em [docs/COMPATIBILITY.pt-BR.md](docs/COMPATIBILITY.pt-BR.md).

## Instale o que você precisa

| Instale | Você ganha | Use quando |
|---|---|---|
| `pip install diagnos` | `diagnos docs`, `version`, `setup`, `help` — sem dependências | uma primeira olhada; ela instala o resto para você |
| `pip install "diagnos[sdk]"` | [o SDK](apps/sdk/README.pt-BR.md) — `from diagnos import Diagnos` | seu código é Python |
| `pip install "diagnos[cli]"` | [a CLI](apps/cli/README.pt-BR.md) — `diagnos login`, `diagnos patients list`, … | scripts, operação, uma olhada rápida |
| `pip install "diagnos[api]"` | [a API REST](apps/api/README.pt-BR.md) — `diagnos-api`, ou a imagem assinada dela | seu sistema fala HTTP, não Python |

Mesmo token, mesma sessão, mesmas garantias: a CLI e a API são cascas finas sobre o SDK — nunca
reimplementam um único byte de criptografia. Um pacote traz os três; um extra só soma as dependências de uma camada.
Ou deixe a base fazer, passo a passo:

```sh
uv tool install diagnos   # ou: pipx install diagnos
diagnos setup sdk         # o SDK no projeto Python daqui, com uv
diagnos setup cli         # todos os comandos para este `diagnos`, com uv
diagnos setup api         # a imagem da API, baixada e verificada pelo digest, com Docker e cosign
```

Todo release é assinado com Sigstore e traz proveniência de build — [verifique](SECURITY.pt-BR.md#verificando-um-release).
Quem programa em outras linguagens ganha os mesmos quatro comandos da base pelos [wrappers](wrappers/README.pt-BR.md).

> [!NOTE]
> Até a `0.2.0` estar no PyPI, instale do código-fonte — [Instalação](docs/guides/install.pt-BR.md) tem os comandos,
> e o [toolchain Rust](https://rustup.rs/) que o build precisa.

## Começando — 60 segundos

**1. Consiga um token.** Um admin do workspace abre *Configurações → Contas de serviço* no app web do diagnos, cria
uma conta de serviço, escolhe os security groups que ela pode ler e copia o token dela — `dgn_sk1_…`, mostrado uma
vez, porque o cofre guarda só as chaves públicas dele.

**2. Guarde-o com segurança, uma vez.**

```sh
diagnos login          # cole: conferido, provado contra o cofre, guardado no chaveiro do sistema (ou no OpenBao)
```

Em CI ou num container, `export DIAGNOS_TOKEN="dgn_sk1_…"` vindo do seu cofre de segredos. Nunca num arquivo.

**3. Use.** Sem etapa de aprovação, sem código para digitar: o token abre a sessão com uma requisição assinada.

```python
from diagnos import Diagnos

with Diagnos() as vault:  # acha o token, abre a sessão
    print(vault.workspace_id)
    print(vault.security_groups)  # os grupos escolhidos para o token
```

```sh
diagnos whoami         # qual token, de onde, e os grupos dele
diagnos patients list  # todo comando abre a própria sessão, sem prompt
diagnos logout         # esquece o token guardado
```

> [!NOTE]
> O token `apikey-` em `DIAGNOS_API_TOKEN` está obsoleto: funciona, com aviso, até **2027-04-15**.
> O [MIGRATING.pt-BR.md](MIGRATING.pt-BR.md#do-token-apikey--para-o-token-de-conta-de-serviço-020) o troca por um
> token.

**4. Vá além.** Pacientes, exames e arquivos pendem do mesmo objeto — `vault.patients`, `vault.exams`, `vault.drives`. O
[início rápido](docs/guides/quickstart.pt-BR.md) vai daqui até o primeiro paciente e o primeiro arquivo cifrados, e
[`examples/`](examples/README.pt-BR.md) tem programas completos para copiar: subir um arquivo, pacientes, exames,
tratamento de erros.

Um nome, três grafias: um **security group** é `security_group=` no SDK (`security_group_id` no que ele devolve),
`--group` / `DIAGNOS_GROUP` na CLI, e `security_group` ou `{sg}` na API.

A semente do token e toda chave privada derivada dela ficam dentro do enclave em Rust do SDK, e nada é gravado em
disco. [Autenticação](docs/guides/authentication.pt-BR.md) mostra o token e onde ele mora, e
[Sessões](docs/guides/sessions.pt-BR.md) como uma sessão abre, expira e reabre sozinha.

## Por que dois tipos de criptografia

Toda requisição é assinada duas vezes — com **Ed25519**, o algoritmo clássico provado ao longo de muitos anos, e com
**ML-DSA-65**, um pós-quântico (FIPS 204) — e o cofre só a aceita quando **as duas** assinaturas conferem. As chaves
que o cofre entrega ao seu processo são seladas do mesmo jeito, para **X25519** e **ML-KEM-768** (FIPS 203) juntos.

Por que os dois? Os algoritmos clássicos são bem conhecidos, mas um computador quântico grande o bastante os quebraria.
Os pós-quânticos resistem a esse computador, mas são novos. Com os dois, um atacante precisa quebrar **os dois** — um
defeito achado amanhã em um deles, ou um computador quântico algum dia, não basta. Um dado clínico gravado hoje
continua protegido amanhã. Você não escolhe nem configura nada disso: o único token carrega as quatro chaves.

## O que vem de graça

- **🔐 Ponta a ponta por padrão** — registros e arquivos são cifrados no seu processo; o cofre vê ciphertext,
  requisições assinadas e URLs pré-assinadas. [Exatamente o que ele vê](docs/guides/security.pt-BR.md#o-que-o-cofre-vê).
- **🛡️ Clássico + pós-quântico** — um token assina com Ed25519 *e* ML-DSA-65 e abre chaves seladas para X25519 *e*
  ML-KEM-768; quebrar um algoritmo não basta. [Por quê](#por-que-dois-tipos-de-criptografia).
- **🧱 Chaves num enclave Rust** — memória travada com `mlock`, guard pages, fora de core dumps, zerada no `fork()` e
  ao descartar, nunca devolvida ao Python como `bytes`. Modelo de ameaça:
  [`apps/sdk/native/README.pt-BR.md`](apps/sdk/native/README.pt-BR.md).
- **🔁 Retentativa e relógio resolvidos** — retentativas idempotentes, sincronia de relógio com o cofre, exceções
  estáveis: [Erros](docs/guides/errors.pt-BR.md).
- **📐 Formatos de bytes travados** — [`docs/PROTOCOL.pt-BR.md`](docs/PROTOCOL.pt-BR.md) é normativo, e vetores de
  teste gerados da implementação de referência do cofre travam cada byte.

## Servidores

Um servidor guarda o token no [OpenBao](https://openbao.org/), não num arquivo de ambiente: o `diagnos login --store
openbao` o guarda uma vez com um token de escrita, e o processo o lê na subida com um token que só pode lê-lo — e
então abre a sessão sem humano, a cada reinício. Manifestos prontos ficam em [`apps/api/deploy/`](apps/api/deploy/README.pt-BR.md): Docker Compose e Kubernetes,
com auto-unseal do OpenBao para AWS KMS, Azure Key Vault, GCP KMS, Transit, Shamir e chave estática.

## Documentação

| Comece aqui | Depois |
|---|---|
| [Início rápido](docs/guides/quickstart.pt-BR.md) · [Instalação](docs/guides/install.pt-BR.md) · [Conceitos](docs/guides/concepts.pt-BR.md) | [Autenticação](docs/guides/authentication.pt-BR.md) · [Sessões](docs/guides/sessions.pt-BR.md) · [Configuração](docs/guides/configuration.pt-BR.md) |
| [Pacientes](docs/guides/patients.pt-BR.md) · [Exames](docs/guides/exams.pt-BR.md) · [Arquivos](docs/guides/files.pt-BR.md) · [Exemplos](examples/README.pt-BR.md) | [Erros](docs/guides/errors.pt-BR.md) · [Modelo de segurança](docs/guides/security.pt-BR.md) |
| [Guia da CLI](docs/guides/cli.pt-BR.md) · [Guia da API REST](docs/guides/api.pt-BR.md) | [Implantação](apps/api/deploy/README.pt-BR.md) · [Protocolo](docs/PROTOCOL.pt-BR.md) · [Compatibilidade](docs/COMPATIBILITY.pt-BR.md) |

O site de desenvolvedores publica estas mesmas páginas em `/dev/docs`, mais uma referência gerada a partir do código —
todo comando, rota e classe. [Como a doc é construída e checada](docs/README.pt-BR.md).

## Portões de qualidade

Todo badge acima é um workflow ou o que um deles mede; todos menos os dois últimos rodam localmente com um comando.

| Badge | O que prova | Localmente |
|---|---|---|
| **CI** | toda camada — base, SDK, CLI, API — passa nos testes no CPython 3.11 e 3.13, mais o enclave Rust; lint (Python, Rust, docstrings bilíngues, documentação), `mypy --strict`, o lockfile, a doc (todo exemplo roda, a referência está em dia), o contrato [Pact](https://pact.io) que o cofre verifica, e os próprios workflows (zizmor, actionlint) | `make check` |
| **Cobertura** | cobertura de ramos combinada do pacote `diagnos` inteiro, com um piso que só sobe | `make cov` |
| **Pacote** | os sete wheels e o sdist constroem, e cada wheel funciona instalado sozinho na própria plataforma — puro, depois com todo extra; as duas imagens constroem | `uv build` |
| **OpenSSF Scorecard** | as práticas de cadeia de suprimentos: dependências fixadas, tokens com privilégio mínimo, releases assinados, proteção de branch | — |

Os releases saem da `main` pelo [`release.yml`](.github/workflows/release.yml): assinaturas Sigstore e proveniência
SLSA em todo arquivo e imagem, um SBOM, PyPI via Trusted Publishing — nenhum segredo de longa duração em lugar nenhum.
O CodeQL analisa todo pull request, e o libFuzzer exercita os parsers do enclave toda semana.

O contrato é guiado pelo consumidor: os testes do SDK gravam
[`contracts/diagnos-sdk-diagnos-vault.json`](contracts/diagnos-sdk-diagnos-vault.json), e o cofre verifica esse
mesmo arquivo contra o código real dele antes de implantar.

```mermaid
flowchart LR
    SDK["Testes do SDK<br/>(mock do Pact, motor Rust)"] -->|gravam| C[("diagnos-sdk-diagnos-vault.json")]
    C -->|repetido contra| V["vault.diagnos.health<br/>verificação do provider"]
```

## Estrutura

```
integration/
├── src/diagnos/       diagnos          o pacote único — `pip install diagnos[…]`
│   ├── _wrapper/      (base)           docs · version · setup · help, só biblioteca padrão
│   ├── …              [sdk]            o SDK: client, crypto, session, transport, resources, models
│   ├── cli/           [cli]            `diagnos …` no seu terminal
│   └── api/           [api]            fachada REST (FastAPI), só mTLS
├── apps/              (por camada)     o guia, os testes e os recursos de cada camada
│   ├── sdk/native/    diagnos._secure  enclave de memória em Rust
│   └── api/deploy/    compose · k8s    manifestos prontos para rodar
├── wrappers/          contract.json    os quatro comandos da base, para toda linguagem · py/: o de Python
├── examples/          NN-nome/main.py  programas completos e executáveis para o SDK
├── contracts/         Pact             contrato do consumidor com o cofre + os testes dele
├── docs/              guides/          a documentação · reference/ gerada a partir do código
│                      PROTOCOL.md      formatos de bytes normativos · COMPATIBILITY.md · site.json
├── scripts/           docs/            as checagens por trás do `make lint`, do `make docs-check` e da CI
└── Dockerfile         api · cli        as duas imagens, construídas a partir do wheel
```

## Como contribuir

Você precisa de [uv](https://docs.astral.sh/uv/), Python 3.11–3.13 e, para construir o enclave do fonte,
[rustup](https://rustup.rs/) — ele instala o Rust que o `rust-toolchain.toml` fixa.

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # instala todo extra, editável, e constrói o enclave Rust
make check   # exatamente o que a CI roda: lint, tipos, testes unitários e de contrato, doc
make         # lista todos os outros alvos
```

Leia o [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md) antes do primeiro pull request. Vindo dos pacotes `imgexam`?
Veja o [MIGRATING.pt-BR.md](MIGRATING.pt-BR.md).

## Segurança

Achou uma vulnerabilidade? Por favor **não** abra issue pública — reporte em privado pelo
[GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new). Detalhes no
[SECURITY.pt-BR.md](SECURITY.pt-BR.md).

---

[Apache-2.0](LICENSE) · [diagnos.health](https://diagnos.health)
