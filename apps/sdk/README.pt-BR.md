# diagnos

[English](README.md) · **Português (Brasil)**

O SDK Python oficial, zero-knowledge, do cofre diagnos (`vault.diagnos.health`). Pacientes, exames e arquivos são
cifrados neste processo, na RAM, antes de um único byte chegar à rede — o cofre só vê ciphertext, requisições
assinadas e URLs pré-assinadas. Este pacote é o único lugar onde essa complexidade mora; `diagnos-cli` e `diagnos-api`
são cascas finas sobre ele.

> [!NOTE]
> **Situação: prévia 0.1.0.** Enrollment, chaves de sessão, assinatura de requisições, o relógio, o lock,
> `vault.patients`, `vault.exams` e `vault.drives` falam o protocolo atual do cofre e são verificados contra ele pelos
> testes de contrato Pact. Limites conhecidos:
> [COMPATIBILITY.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.pt-BR.md).

O objetivo é o seu código ler assim:

```python
from diagnos import Diagnos

with Diagnos() as vault:
    for row in vault.patients.list():
        patient = vault.patients.get(row.id)
        print(patient.record.legal_name)
```

## Instalação

```sh
pip install diagnos
pip install "diagnos[openbao]"          # com auto-unseal via OpenBao, para servidores
export DIAGNOS_API_TOKEN="apikey-…"     # emitido por um admin do workspace
```

> [!NOTE]
> Ainda não está no PyPI. Até o primeiro release, instale do código-fonte — construir o enclave exige um
> [toolchain Rust](https://rustup.rs/):
> `pip install "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"`

## A primeira sessão

```python
from diagnos import Diagnos

vault = Diagnos()  # lê DIAGNOS_API_TOKEN; ainda sem rede
vault.unlock()  # imprime um link + um código de 6 dígitos, espera um admin aprovar

for row in vault.patients.list():
    print(row.id, row.summary.display_name if row.summary else "—")
```

O token diz *qual* service account está pedindo; a aprovação decide o que este processo pode decifrar. Você raramente
chama `unlock()` à mão — o primeiro uso de `vault.patients`, `vault.exams` ou `vault.drives` desbloqueia de forma
preguiçosa — e um servidor que precisa reiniciar sem uma pessoa usa o auto-unseal com OpenBao, uma troca deliberada
que o guia de sessões detalha.

## O que tem dentro

- **`vault.patients`, `vault.exams`** — documentos versionados e selados, lidos e gravados exatamente como o app web
  os lê e grava, com registros à prova de erro de digitação e gravações concorrentes seguras.
- **`vault.drives`** — arquivos e pastas sob as próprias chaves, subidos num `PUT` ou em partes, baixados em stream.
- **Um enclave de memória em Rust** — toda chave vive em memória travada, nunca vai para o swap nem para um dump, é
  zerada no `fork()` e ao descartar, e nunca volta ao Python como `bytes`.
- **O protocolo resolvido para você** — assinatura de requisições, diferença de relógio, retentativa de tudo que é
  seguro retentar, uma classe de exceção por decisão que você precisa tomar.

## Guias

| Guia | |
|---|---|
| [Início rápido](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/quickstart.pt-BR.md) | do token ao primeiro paciente e arquivo cifrados |
| [Conceitos](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/concepts.pt-BR.md) | workspaces, grupos, chaves, versões, rascunhos, nós |
| [Autenticação](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/authentication.pt-BR.md) | o token, o link e o código de enrollment, a aprovação |
| [Sessões](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/sessions.pt-BR.md) | unlock, lock, expiração, auto-unseal com OpenBao |
| [Pacientes](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/patients.pt-BR.md) · [Exames](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/exams.pt-BR.md) · [Arquivos](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/files.pt-BR.md) | os três recursos |
| [Erros](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/errors.pt-BR.md) | toda exceção, o que é retentado, diferença de relógio |
| [Configuração](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/configuration.pt-BR.md) | toda variável de ambiente e o `Settings` |
| [Modelo de segurança](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/security.pt-BR.md) | o que o cofre vê, o que o enclave protege |
| [Referência do SDK](https://github.com/diagnos-tech/integration/blob/develop/docs/reference/sdk.json) | toda classe e função pública, gerada a partir do código |

O modelo de ameaça do próprio enclave está em [`native/README.pt-BR.md`](native/README.pt-BR.md), e o contrato de fio
normativo no [PROTOCOL.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/docs/PROTOCOL.pt-BR.md).

## Desenvolvimento

```sh
make sync                       # instala tudo e constrói o enclave Rust (precisa de cargo)
uv run --package diagnos pytest apps/sdk/tests
make lint                       # ruff, cargo fmt/clippy, docs
make types                      # mypy --strict
```

Rode `make help` na raiz do repositório para ver todos os alvos. Instalar pelo PyPI não precisa de Rust: os wheels
trazem o enclave compilado para cada plataforma (abi3, CPython ≥ 3.11). Construir do código-fonte precisa de um
toolchain Rust stable (`rustup`), que o `uv sync` invoca via maturin; depois de uma edição em Rust,
`uv sync --reinstall-package diagnos` o reconstrói.
