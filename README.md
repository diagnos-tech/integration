<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/diagnos-lockup-white.svg">
    <img src=".github/assets/diagnos-lockup-gradient.svg" alt="diagnos" width="260">
  </picture>
</p>

<p align="center">
  <b>Zero-knowledge SDK, CLI and API for the diagnos vault.</b><br>
  <sub>SDK, CLI e API zero-knowledge para o cofre diagnos.</sub>
</p>

<hr>

<p align="center">
  <a href="https://pypi.org/project/diagnos/"><img alt="diagnos no PyPI" src="https://img.shields.io/pypi/v/diagnos?label=diagnos&color=8b5cf6"></a>
  <a href="https://pypi.org/project/diagnos-cli/"><img alt="diagnos-cli no PyPI" src="https://img.shields.io/pypi/v/diagnos-cli?label=diagnos-cli&color=0ea5e9"></a>
  <a href="https://pypi.org/project/diagnos-api/"><img alt="diagnos-api no PyPI" src="https://img.shields.io/pypi/v/diagnos-api?label=diagnos-api&color=14b8a6"></a>
  <a href="https://pypi.org/project/diagnos/"><img alt="python" src="https://img.shields.io/pypi/pyversions/diagnos?color=2dd4bf"></a>
  <a href="LICENSE"><img alt="licença" src="https://img.shields.io/badge/license-Apache--2.0-64748b"></a>
</p>

<p align="center">
  <a href="sdk/README.md"><b>SDK</b></a> ·
  <a href="cli/README.md"><b>CLI</b></a> ·
  <a href="api/README.md"><b>API</b></a> ·
  <a href="docs/PROTOCOL.md">Protocol</a> ·
  <a href="CONVENTIONS.md">Contributing</a> ·
  <a href="#security--segurança">Security</a>
</p>

<br>

🇺🇸 Three open-source Python packages for talking to the diagnos vault without ever handling a signed URL, an HMAC
or a key envelope yourself. Everything clinical is encrypted **inside your process** before it touches the network —
the vault only ever sees ciphertext. These packages make that the *easy* path.

🇧🇷 Três pacotes Python de código aberto para falar com o cofre diagnos sem nunca lidar com URL assinada, HMAC ou
envelope de chave. Tudo que é clínico é cifrado **dentro do seu processo** antes de tocar a rede — o cofre só vê
ciphertext. Estes pacotes fazem disso o caminho *fácil*.

<br>

## Pick your door · Escolha sua porta

| Package · Pacote | 🇺🇸 When to use · 🇧🇷 Quando usar | Install · Instalação |
|---|---|---|
| [**`diagnos`**](sdk/README.md) — SDK | Your code is Python. · Seu código é Python. | `pip install diagnos` |
| [**`diagnos-cli`**](cli/README.md) — CLI | Scripts, ops, a quick look. · Scripts, operação, uma olhada rápida. | `pipx install diagnos-cli` |
| [**`diagnos-api`**](api/README.md) — API | Your system speaks HTTP, not Python. · Seu sistema fala HTTP, não Python. | [Docker / Kubernetes](api/deploy/README.md) |

🇺🇸 Same token, same approval flow, same guarantees. The CLI and the API are thin shells over the SDK — they never
reimplement a single byte of cryptography.
🇧🇷 Mesmo token, mesmo fluxo de aprovação, mesmas garantias. A CLI e a API são cascas finas sobre o SDK — nunca
reimplementam um único byte de criptografia.

<br>

## Quick start · Começando

**1.** 🇺🇸 Ask a workspace admin for a service-account token. · 🇧🇷 Peça a um admin do workspace um token de service account.

```sh
export DIAGNOS_API_TOKEN="apikey-…"
```

**2.** 🇺🇸 Pick one. · 🇧🇷 Escolha um.

```python
# SDK
from diagnos import Diagnos

with Diagnos() as vault:
    for index in vault.patients.list():
        patient = vault.patients.get(index.document_id)  # 🇺🇸 decrypted in RAM · 🇧🇷 decifrado na RAM
        print(patient.record.legal_name)
```

```sh
# CLI
diagnos login
diagnos --json patients list --group sg_oncology | jq '.items[].document_id'
```

```sh
# API — mutual TLS only · só mTLS
curl --cert client.pem --key client-key.pem --cacert clients-ca.pem \
  https://diagnos-api.internal:8443/v1/patients
```

**3.** 🇺🇸 The first run prints a link and a 6-digit code. An admin approves it in the web app — and you are in.
🇧🇷 A primeira execução imprime um link e um código de 6 dígitos. Um admin aprova no app web — e pronto.

<br>

## How a session is born · Como nasce uma sessão

```mermaid
sequenceDiagram
    autonumber
    participant P as Your process (SDK)
    participant V as vault.diagnos.com
    actor A as Workspace admin
    participant W as diagnos web app

    P->>P: generate X25519 + ML-KEM-768 key pair, in RAM
    P->>V: register public keys + runtime description
    V-->>P: approval link + 6-digit code
    P-->>A: prints link + code
    A->>W: opens link, checks the runtime, types the code, picks groups
    W->>V: group keys sealed to the SDK's public keys
    P->>V: poll
    V-->>P: sealed group keys + session keys
    Note over P: opens both with private keys<br/>that never left the process → unlocked
```

🇺🇸 Private keys never leave the process, and nothing is written to disk. Stop the process and the next one needs a
new approval — that is the design, not a limitation. For pods and cron jobs, see [auto-unseal](#servers-without-a-human--servidores-sem-humano) below.
🇧🇷 As chaves privadas nunca saem do processo, e nada é gravado em disco. Pare o processo e o próximo precisa de uma
nova aprovação — isso é o desenho, não uma limitação. Para pods e cron jobs, veja [auto-unseal](#servers-without-a-human--servidores-sem-humano) abaixo.

<br>

## What you get for free · O que vem de graça

- **🔐 End-to-end, by default · Ponta a ponta, por padrão** — 🇺🇸 patients, exams and files (DICOM, images, video, PDF)
  are encrypted in your process; the vault sees ciphertext, signed requests and presigned URLs. 🇧🇷 pacientes, exames e
  arquivos são cifrados no seu processo; o cofre vê ciphertext, requisições assinadas e URLs pré-assinadas.
- **🛡️ Post-quantum hybrid · Híbrido pós-quântico** — 🇺🇸 enrollment uses X25519 + ML-KEM-768, so a recorded session
  stays safe against a future quantum adversary. 🇧🇷 o enrollment usa X25519 + ML-KEM-768, então uma sessão gravada
  continua segura contra um adversário quântico futuro.
- **🧱 Keys in a Rust enclave · Chaves num enclave Rust** — 🇺🇸 `mlock`ed memory, guard pages, excluded from core
  dumps, zeroed on `fork()` and on drop, never handed back to Python as `bytes`. 🇧🇷 memória travada com `mlock`,
  guard pages, fora de core dumps, zerada no `fork()` e ao descartar, nunca devolvida ao Python como `bytes`.
- **📦 Big files, no thinking · Arquivo grande, sem pensar** — 🇺🇸 large uploads are split into encrypted parts
  automatically. 🇧🇷 uploads grandes são partidos em pedaços cifrados automaticamente.
- **🔁 Retries and clock skew handled · Retentativa e relógio resolvidos** — 🇺🇸 idempotent retries, time sync with the
  vault, stable exceptions. 🇧🇷 retentativa idempotente, sincronia de relógio com o cofre, exceções estáveis.
- **📐 Pinned byte formats · Formatos de bytes travados** — 🇺🇸 [`docs/PROTOCOL.md`](docs/PROTOCOL.md) is normative;
  test vectors generated from the vault's own reference pin every byte. 🇧🇷 [`docs/PROTOCOL.md`](docs/PROTOCOL.md) é
  normativo; vetores de teste gerados da referência do próprio cofre travam cada byte.

<br>

## Servers without a human · Servidores sem humano

🇺🇸 A human approval on every restart is fine for a laptop; it is not fine for a Kubernetes pod. Set two variables and
the SDK saves its unlocked session to [OpenBao](https://openbao.org/)'s encrypted KV right after enrollment, then
restores from there on every start — no human, until the saved session expires.
🇧🇷 Uma aprovação humana a cada reinício serve num notebook; não serve num pod Kubernetes. Defina duas variáveis e o SDK
salva a sessão desbloqueada no KV cifrado do [OpenBao](https://openbao.org/) logo após o enrollment, e restaura de lá a
cada subida — sem humano, até a sessão salva expirar.

```sh
pip install "diagnos[openbao]"
export OPENBAO_ADDR="https://openbao.internal:8200"
export OPENBAO_TOKEN="…"   # 🇺🇸 scoped to one path, nothing wider · 🇧🇷 restrito a um path, nada mais amplo
```

> [!WARNING]
> 🇺🇸 This is a deliberate trade: whoever can read that OpenBao path can decrypt exactly what this process can.
> Read [the full tradeoff](sdk/README.md#auto-unseal-with-openbao--auto-unseal-com-openbao) before turning it on.
> 🇧🇷 É uma troca deliberada: quem ler aquele path do OpenBao decifra exatamente o que este processo decifra.
> Leia [o tradeoff completo](sdk/README.md#auto-unseal-with-openbao--auto-unseal-com-openbao) antes de ligar.

🇺🇸 Ready-made manifests live in [`api/deploy/`](api/deploy/README.md): Docker Compose and Kubernetes, with OpenBao
auto-unseal for AWS KMS, Azure Key Vault, GCP KMS, Transit, Shamir and static keys.
🇧🇷 Manifestos prontos ficam em [`api/deploy/`](api/deploy/README.md): Docker Compose e Kubernetes, com auto-unseal do
OpenBao para AWS KMS, Azure Key Vault, GCP KMS, Transit, Shamir e chave estática.

<br>

## Repository layout · Estrutura

```
integration/
├── sdk/           diagnos           🇺🇸 the library — everything lives here   🇧🇷 a biblioteca — tudo vive aqui
│   └── native/    diagnos._secure   🇺🇸 Rust memory enclave                   🇧🇷 enclave de memória em Rust
├── cli/           diagnos-cli       🇺🇸 `diagnos …` in your terminal          🇧🇷 `diagnos …` no seu terminal
├── api/           diagnos-api       🇺🇸 REST facade (FastAPI), mTLS only      🇧🇷 fachada REST (FastAPI), só mTLS
│   └── deploy/    compose · k8s     🇺🇸 ready-to-run manifests                🇧🇷 manifestos prontos para rodar
└── docs/          PROTOCOL.md       🇺🇸 normative byte formats                🇧🇷 formatos de bytes normativos
```

<br>

## Contributing · Contribuindo

| 🇺🇸 You need · 🇧🇷 Você precisa | |
|---|---|
| [uv](https://docs.astral.sh/uv/) | 🇺🇸 one venv for the whole workspace · 🇧🇷 um venv para o workspace inteiro |
| Python 3.11 – 3.13 | |
| [Rust](https://rustup.rs/) stable | 🇺🇸 only to build from source — PyPI wheels are prebuilt · 🇧🇷 só para construir do fonte — os wheels do PyPI vêm prontos |

```sh
git clone https://github.com/diagnos/integration && cd integration
make sync    # 🇺🇸 installs everything, builds the Rust enclave · 🇧🇷 instala tudo, constrói o enclave Rust
make check   # 🇺🇸 lint + types + tests, Python and Rust — what CI runs · 🇧🇷 lint + tipos + testes, Python e Rust — o que a CI roda
```

| `make` | 🇺🇸 · 🇧🇷 |
|---|---|
| `lint` | ruff, `cargo fmt`, `cargo clippy -D warnings`, bilingual-docstring check · checagem de docstring bilíngue |
| `types` | `mypy --strict` over · sobre `sdk`, `cli`, `api` |
| `test` | pytest (3 packages · 3 pacotes) + `cargo test` |
| `check` | 🇺🇸 all of the above · 🇧🇷 tudo acima |

🇺🇸 Read [`CONVENTIONS.md`](CONVENTIONS.md) before your first pull request — short version: every docstring is
bilingual (🇺🇸 + 🇧🇷), `cli` and `api` import **only** `diagnos`, and every `unsafe` Rust block lives in a few audited modules with a `SAFETY:` note.
🇧🇷 Leia [`CONVENTIONS.md`](CONVENTIONS.md) antes do primeiro pull request — versão curta: toda docstring é bilíngue
(🇺🇸 + 🇧🇷), `cli` e `api` importam **só** `diagnos`, e todo bloco `unsafe` em Rust fica em poucos módulos auditados, com um comentário `SAFETY:`.

<br>

## Security · Segurança

🇺🇸 Found a vulnerability? Please **do not** open a public issue — report it privately through
[GitHub Security Advisories](https://github.com/diagnos/integration/security/advisories/new).
🇧🇷 Achou uma vulnerabilidade? Por favor **não** abra issue pública — reporte em privado pelo
[GitHub Security Advisories](https://github.com/diagnos/integration/security/advisories/new).

🇺🇸 The enclave's threat model — what is and is not guaranteed — is in [`sdk/native/README.md`](sdk/native/README.md).
🇧🇷 O modelo de ameaça do enclave — o que é e o que não é garantido — está em [`sdk/native/README.md`](sdk/native/README.md).

<br>

<p align="center">
  <sub><a href="LICENSE">Apache-2.0</a> · <a href="https://diagnos.com">diagnos.com</a></sub>
</p>
