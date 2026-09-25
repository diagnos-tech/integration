<h1 align="center">diagnos · integration</h1>

<p align="center"><b>SDK, CLI e API REST zero-knowledge para o cofre diagnos.</b></p>

<p align="center">

[English](README.md) · **Português (Brasil)**

</p>

<p align="center">
  <a href="https://github.com/diagnos-tech/integration/actions/workflows/unit-tests.yml?query=branch%3Adevelop"><img alt="Testes unitários" src="https://github.com/diagnos-tech/integration/actions/workflows/unit-tests.yml/badge.svg?branch=develop"></a>
  <a href="https://github.com/diagnos-tech/integration/actions/workflows/unit-tests.yml?query=branch%3Adevelop"><img alt="Cobertura" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdiagnos-tech%2Fintegration%2Fbadges%2Fcoverage.json"></a>
  <a href="https://github.com/diagnos-tech/integration/actions/workflows/contract-tests.yml?query=branch%3Adevelop"><img alt="Testes de contrato" src="https://github.com/diagnos-tech/integration/actions/workflows/contract-tests.yml/badge.svg?branch=develop"></a>
  <a href="https://github.com/diagnos-tech/integration/actions/workflows/ci.yml?query=branch%3Adevelop"><img alt="CI" src="https://github.com/diagnos-tech/integration/actions/workflows/ci.yml/badge.svg?branch=develop"></a>
  <a href="pyproject.toml"><img alt="Python 3.11 | 3.12 | 3.13" src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab"></a>
  <a href="LICENSE"><img alt="Licença: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-64748b"></a>
</p>

<p align="center">
  <a href="apps/sdk/README.pt-BR.md"><b>SDK</b></a> ·
  <a href="apps/cli/README.pt-BR.md"><b>CLI</b></a> ·
  <a href="apps/api/README.pt-BR.md"><b>API</b></a> ·
  <a href="docs/PROTOCOL.pt-BR.md">Protocolo</a> ·
  <a href="contracts/README.pt-BR.md">Testes de contrato</a> ·
  <a href="CONTRIBUTING.pt-BR.md">Como contribuir</a> ·
  <a href="SECURITY.pt-BR.md">Segurança</a>
</p>

Três pacotes Python de código aberto para falar com o cofre diagnos sem nunca lidar com URL assinada, HMAC ou envelope
de chave. Tudo que é clínico é cifrado **dentro do seu processo** antes de tocar a rede — o cofre só vê ciphertext.
Estes pacotes fazem disso o caminho *fácil*.

> [!WARNING]
> **Situação: prévia 0.1.0.** Enrollment, sessões e assinatura de requisições são verificados contra o cofre pelos
> [testes de contrato](contracts/README.pt-BR.md). As APIs de pacientes, exames e arquivos ainda implementam uma
> revisão anterior do protocolo do cofre e **ainda não são compatíveis com o vault.diagnos.health** — leia
> [docs/COMPATIBILITY.pt-BR.md](docs/COMPATIBILITY.pt-BR.md) antes de construir em cima delas.

## Escolha seu pacote

| Pacote | Use quando | Instalação |
|---|---|---|
| [**`diagnos`**](apps/sdk/README.pt-BR.md) — SDK | Seu código é Python. | `pip install diagnos` |
| [**`diagnos-cli`**](apps/cli/README.pt-BR.md) — CLI | Scripts, operação, uma olhada rápida. | `pipx install diagnos-cli` |
| [**`diagnos-api`**](apps/api/README.pt-BR.md) — API REST | Seu sistema fala HTTP, não Python. | [Docker / Kubernetes](apps/api/deploy/README.pt-BR.md) |

Mesmo token, mesmo fluxo de aprovação, mesmas garantias. A CLI e a API são cascas finas sobre o SDK — nunca
reimplementam um único byte de criptografia.

> [!NOTE]
> Ainda não está no PyPI. Até o primeiro release, instale do fonte (construir o SDK exige um
> [toolchain Rust](https://rustup.rs/)):
> `pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=sdk"`

## Começando

**1. Consiga um token.** Peça a um admin do workspace um token de service account:

```sh
export DIAGNOS_API_TOKEN="apikey-…"
```

**2. Faça o enrollment.** A primeira execução imprime um link e um código de 6 dígitos; um admin aprova no app web do
diagnos e escolhe quais security groups este processo pode ler.

```python
from diagnos import Diagnos

with Diagnos() as vault:  # faz enrollment na entrada: imprime o link de aprovação + código
    print(vault.workspace_id)
    print(vault.security_groups)  # os grupos que o admin concedeu
```

```sh
diagnos login          # o mesmo enrollment, pelo terminal
diagnos status         # token, OpenBao e versão do SDK
```

**3. Use.** Pacientes, exames e arquivos penduram no mesmo objeto — `vault.patients`, `vault.exams`,
`vault.drives` — veja o [guia do SDK](apps/sdk/README.pt-BR.md) (prévia, veja a situação acima).

## Como nasce uma sessão

```mermaid
sequenceDiagram
    autonumber
    participant P as Seu processo (SDK)
    participant V as vault.diagnos.health
    actor A as Admin do workspace
    participant W as App web do diagnos

    P->>P: gera par de chaves X25519 + ML-KEM-768, na RAM
    P->>V: registra as chaves públicas + descrição do runtime
    V-->>P: link de aprovação + código de 6 dígitos
    P-->>A: imprime link + código
    A->>W: abre o link, confere o runtime, digita o código, escolhe os grupos
    W->>V: chaves dos grupos seladas para as chaves públicas do SDK
    P->>V: poll
    V-->>P: chaves dos grupos seladas + chaves de sessão seladas
    Note over P: abre as duas com as chaves privadas<br/>que nunca saíram do processo → desbloqueado
```

As chaves privadas nunca saem do processo, e nada é gravado em disco. Pare o processo e o próximo precisa de uma nova
aprovação — isso é o desenho, não uma limitação. Para pods e cron jobs, veja
[servidores sem humano](#servidores-sem-humano).

## O que vem de graça

- **🔐 Ponta a ponta por padrão** — registros e arquivos são cifrados no seu processo; o cofre vê ciphertext,
  requisições assinadas e URLs pré-assinadas.
- **🛡️ Híbrido pós-quântico** — o enrollment usa X25519 + ML-KEM-768, então uma sessão gravada continua segura contra
  um adversário quântico futuro.
- **🧱 Chaves num enclave Rust** — memória travada com `mlock`, guard pages, fora de core dumps, zerada no `fork()` e
  ao descartar, nunca devolvida ao Python como `bytes`. Modelo de ameaça:
  [`apps/sdk/native/README.pt-BR.md`](apps/sdk/native/README.pt-BR.md).
- **🔁 Retentativa e relógio resolvidos** — retentativas idempotentes, sincronia de relógio com o cofre, exceções
  estáveis.
- **📐 Formatos de bytes travados** — [`docs/PROTOCOL.pt-BR.md`](docs/PROTOCOL.pt-BR.md) é normativo, e vetores de
  teste gerados da implementação de referência do cofre travam cada byte.

## Servidores sem humano

Uma aprovação humana a cada reinício serve num notebook; não serve num pod Kubernetes. Defina duas variáveis e o SDK
salva a sessão desbloqueada no KV cifrado do [OpenBao](https://openbao.org/) logo após o enrollment, e restaura de lá a
cada subida — sem humano, até a sessão salva expirar.

```sh
pip install "diagnos[openbao]"
export OPENBAO_ADDR="https://openbao.internal:8200"
export OPENBAO_TOKEN="…"   # restrito a um path, nada mais amplo
```

> [!WARNING]
> É uma troca deliberada: quem ler aquele path do OpenBao decifra exatamente o que este processo decifra. Leia
> [o tradeoff completo](apps/sdk/README.pt-BR.md#auto-unseal-com-openbao) antes de ligar.

Manifestos prontos ficam em [`apps/api/deploy/`](apps/api/deploy/README.pt-BR.md): Docker Compose e Kubernetes, com auto-unseal
do OpenBao para AWS KMS, Azure Key Vault, GCP KMS, Transit, Shamir e chave estática.

## Portões de qualidade

Todo badge acima é um workflow que você roda localmente com um comando.

| Badge | O que prova | Localmente |
|---|---|---|
| **Unit tests** | os três pacotes no CPython 3.11–3.13, mais o enclave Rust | `make test` |
| **Coverage** | cobertura de ramos combinada de `diagnos`, `diagnos-cli` e `diagnos-api`, com um piso que só sobe | `make cov` |
| **Contract tests** | o SDK manda e lê exatamente o que o contrato [Pact](https://pact.io) commitado diz (motor Rust `pact_ffi`) | `make contract` |
| **CI** | lint (Python, Rust, docstrings bilíngues, documentação), `mypy --strict`, lockfile | `make lint types` |

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
├── apps/
│   ├── sdk/           diagnos          a biblioteca — tudo vive aqui
│   │   └── native/    diagnos._secure  enclave de memória em Rust
│   ├── cli/           diagnos-cli      `diagnos …` no seu terminal
│   └── api/           diagnos-api      fachada REST (FastAPI), só mTLS
│       └── deploy/    compose · k8s    manifestos prontos para rodar
├── contracts/         Pact             contrato do consumidor com o cofre + os testes dele
├── docs/              PROTOCOL.md      formatos de bytes normativos · COMPATIBILITY.md
└── scripts/                            as checagens por trás do `make lint` e da CI
```

## Como contribuir

Você precisa de [uv](https://docs.astral.sh/uv/), Python 3.11–3.13 e, para construir o enclave do fonte,
[Rust](https://rustup.rs/) stable.

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # instala tudo e constrói o enclave Rust
make check   # exatamente o que a CI roda: lint, tipos, testes unitários e de contrato
make         # lista todos os outros alvos
```

Leia o [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md) antes do primeiro pull request. Vindo dos pacotes `imgexam`?
Veja o [MIGRATING.pt-BR.md](MIGRATING.pt-BR.md).

## Segurança

Achou uma vulnerabilidade? Por favor **não** abra issue pública — reporte em privado pelo
[GitHub Security Advisories](https://github.com/diagnos-tech/integration/security/advisories/new). Detalhes no
[SECURITY.pt-BR.md](SECURITY.pt-BR.md).

<p align="center"><sub><a href="LICENSE">Apache-2.0</a> · <a href="https://diagnos.health">diagnos.health</a></sub></p>
