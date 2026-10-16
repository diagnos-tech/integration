# diagnos · SDK

[English](README.md) · **Português (Brasil)**

O SDK Python oficial, zero-knowledge, do cofre diagnos (`vault.diagnos.health`). Pacientes, exames e arquivos são
cifrados neste processo, na RAM, antes de um único byte chegar à rede — o cofre só vê ciphertext, requisições
assinadas e URLs pré-assinadas. O SDK é o único lugar onde essa complexidade mora; a linha de comando e a API REST são
cascas finas sobre ele. Ele é o extra `sdk` do pacote único `diagnos`: o código dele é o topo de `src/diagnos`, e
`from diagnos import Diagnos` o carrega no primeiro uso.

> [!NOTE]
> **Situação: prévia 0.1.0.** O token de conta de serviço, chaves de sessão, assinatura de requisições, o relógio, o lock,
> `vault.patients`, `vault.exams` e `vault.drives` falam o protocolo atual do cofre e são verificados contra ele pelos
> testes de contrato Pact. Limites conhecidos:
> [COMPATIBILITY.pt-BR.md](https://github.com/diagnos-tech/integration/blob/main/docs/COMPATIBILITY.pt-BR.md).

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
uv add "diagnos[sdk]"                   # ou: pip install "diagnos[sdk]" — ou deixe o `diagnos setup sdk` fazer
uv add "diagnos[sdk,openbao]"           # com o OpenBao, onde um servidor guarda o token
export DIAGNOS_TOKEN="dgn_sk1_…"        # emitido por um admin do workspace — ou `diagnos login`, que o guarda no chaveiro
```

Sem o extra `sdk`, `import diagnos` continua funcionando (é a instalação base), e `from diagnos import Diagnos` lança
`MissingExtraError` com o comando que o soma.

> [!NOTE]
> Até a `0.1.0` estar no PyPI, instale do código-fonte — construir o enclave exige um
> [toolchain Rust](https://rustup.rs/):
> `pip install "diagnos[sdk] @ git+https://github.com/diagnos-tech/integration@develop"`

## A primeira sessão

```python
from diagnos import Diagnos

vault = Diagnos()  # acha o token (DIAGNOS_TOKEN, o chaveiro, o OpenBao); ainda sem rede
vault.unlock()  # uma requisição assinada abre a sessão — sem aprovação, sem código

for row in vault.patients.list():
    print(row.id, row.summary.display_name if row.summary else "—")
```

O token diz *qual* service account está pedindo e carrega a chave do que ela pode decifrar: os grupos escolhidos
quando um admin o criou. Toda requisição é assinada com Ed25519 e ML-DSA-65 juntos, então quebrar um algoritmo — ou um
computador quântico um dia — não basta. Você raramente chama `unlock()` à mão: o primeiro uso de `vault.patients`,
`vault.exams` ou `vault.drives` desbloqueia de forma preguiçosa.

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
| [Início rápido](https://github.com/diagnos-tech/integration/blob/main/docs/guides/quickstart.pt-BR.md) | do token ao primeiro paciente e arquivo cifrados |
| [Conceitos](https://github.com/diagnos-tech/integration/blob/main/docs/guides/concepts.pt-BR.md) | workspaces, grupos, chaves, versões, rascunhos, nós |
| [Autenticação](https://github.com/diagnos-tech/integration/blob/main/docs/guides/authentication.pt-BR.md) | o token, onde ele mora, por que clássico + pós-quântico |
| [Sessões](https://github.com/diagnos-tech/integration/blob/main/docs/guides/sessions.pt-BR.md) | unlock, lock, expiração, auto-unseal com OpenBao |
| [Pacientes](https://github.com/diagnos-tech/integration/blob/main/docs/guides/patients.pt-BR.md) · [Exames](https://github.com/diagnos-tech/integration/blob/main/docs/guides/exams.pt-BR.md) · [Arquivos](https://github.com/diagnos-tech/integration/blob/main/docs/guides/files.pt-BR.md) | os três recursos |
| [Erros](https://github.com/diagnos-tech/integration/blob/main/docs/guides/errors.pt-BR.md) | toda exceção, o que é retentado, diferença de relógio |
| [Configuração](https://github.com/diagnos-tech/integration/blob/main/docs/guides/configuration.pt-BR.md) | toda variável de ambiente e o `Settings` |
| [Modelo de segurança](https://github.com/diagnos-tech/integration/blob/main/docs/guides/security.pt-BR.md) | o que o cofre vê, o que o enclave protege |
| [Referência do SDK](https://github.com/diagnos-tech/integration/blob/main/docs/reference/sdk.json) | toda classe e função pública, gerada a partir do código |

O modelo de ameaça do próprio enclave está em [`native/README.pt-BR.md`](native/README.pt-BR.md), e o contrato de fio
normativo no [PROTOCOL.pt-BR.md](https://github.com/diagnos-tech/integration/blob/main/docs/PROTOCOL.pt-BR.md).

## Desenvolvimento

```sh
make sync                       # instala todo extra e constrói o enclave Rust (precisa do rustup)
uv run pytest apps/sdk/tests
make lint                       # ruff, cargo fmt/clippy, docs
make types                      # mypy --strict
```

Rode `make help` na raiz do repositório para ver todos os alvos. Instalar pelo PyPI não precisa de Rust: os wheels
trazem o enclave compilado para cada plataforma (abi3, CPython ≥ 3.11). Construir do código-fonte precisa do Rust
que o `rust-toolchain.toml` fixa (o `rustup` o instala), que o `uv sync` invoca via maturin; ele reconstrói o enclave
sempre que as fontes mudam.
