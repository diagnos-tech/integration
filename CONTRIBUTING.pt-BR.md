# Como contribuir

[English](CONTRIBUTING.md) · **Português (Brasil)**

Obrigado por considerar contribuir com `diagnos`, `diagnos-cli` ou `diagnos-api`. Este documento é o guia prático:
como preparar o workspace, o ciclo que você roda enquanto trabalha, o que a CI verifica e como reproduzir cada
checagem localmente, as convenções de código herdadas do histórico deste repositório, e a checklist de pull request.
Para os padrões de comportamento que valem para todo mundo, veja [`CODE_OF_CONDUCT.pt-BR.md`](CODE_OF_CONDUCT.pt-BR.md).
Para reportar uma vulnerabilidade, veja [`SECURITY.pt-BR.md`](SECURITY.pt-BR.md) em vez de abrir uma issue.

## Pré-requisitos

| Você precisa | Por quê |
|---|---|
| [uv](https://docs.astral.sh/uv/) | um venv para o workspace inteiro (`sdk`, `cli`, `api`) |
| Python 3.11 – 3.13 | as três versões de CPython contra as quais a CI testa |
| [Rust](https://rustup.rs/) stable | só para construir o `sdk/native` (o enclave de memória) a partir do fonte — os wheels do PyPI vêm prontos |

Você não precisa de Rust instalado para usar os pacotes a partir do PyPI; precisa dele para construir o `diagnos` a
partir de um checkout, porque o `make sync` compila o `sdk/native` para você.

## Primeira preparação

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # instala tudo e constrói o enclave Rust
make check   # lint + tipos + testes + checagem de contrato — o que a CI roda
```

Se `make check` fica verde num clone recém-feito, seu ambiente bate com o da CI.

## O ciclo do dia a dia

```sh
make fmt        # formata e corrige automaticamente Python (ruff) e Rust (cargo fmt)
make test       # testes unitários: os três pacotes Python + o enclave Rust
make cov        # testes unitários com um relatório de cobertura combinado (htmlcov/)
make contract   # testes de consumidor Pact; regera contracts/*.json
```

Rode `make help` a qualquer momento para listar todo alvo com uma descrição de uma linha.

## O que a CI roda, e como reproduzir localmente

A CI é três workflows, cada um respondendo uma pergunta. `make check` roda os mesmos quatro passos na mesma ordem,
então um `make check` verde na sua máquina significa um PR verde.

| Workflow | Responde | Equivalente local |
|---|---|---|
| `CI` (`.github/workflows/ci.yml`) | O código passa nas checagens estáticas e no type-check? | `make lint` (ruff, `cargo fmt --check`, `cargo clippy -D warnings`, checagem de docstring bilíngue, checagem de pares/links da documentação) + `make types` (`mypy --strict` sobre os pacotes, os testes de contrato e `scripts`) |
| `Unit tests` (`.github/workflows/unit-tests.yml`) | Os três pacotes Python e o enclave Rust passam nos próprios testes, em todo CPython suportado, sem o piso de cobertura cair? | `make cov` (ou `make test` para uma passada mais rápida, sem o relatório de cobertura combinado) |
| `Contract tests` (`.github/workflows/contract-tests.yml`) | O SDK ainda fala o contrato HTTP que o cofre verifica? | `make contract-check` |

`make check` roda `lint`, `types`, `test` e `contract-check` nessa ordem — é exatamente o que os três workflows
rodam, só que num único comando na sua máquina.

## Convenções de código

Estas regras valem para código (arquivos `.py` e `.rs`); moravam antes em `CONVENTIONS.md`, que este documento
substitui.

- **Docstrings bilíngues.** Todo módulo, classe e função pública carrega uma docstring com um parágrafo em inglês
  prefixado `🇺🇸` seguido do parágrafo em português prefixado `🇧🇷`. Comentário em linha segue o mesmo par em linhas
  consecutivas. Comentário explica o **porquê** (a ameaça, o custo, a restrição do protocolo), nunca repete o
  código. Comentários de doc em Rust (`//!` de módulo, `///` de item) seguem a mesma regra à risca.
  `scripts/check_bilingual.py` (parte do `make lint`) derruba o build quando uma docstring ou comentário de doc está
  sem uma das bandeiras.

  ```python
  def sign(request: CanonicalRequest, sign_key: bytes) -> str:
      """🇺🇸 HMAC-SHA512 over the canonical string, hex-encoded.

      The vault reconstructs the same string from the raw request; any byte we
      normalize differently is a 401, so this mirrors `canonical.ts` verbatim.

      🇧🇷 HMAC-SHA512 sobre a string canônica, em hex.

      O cofre reconstrói a mesma string a partir da requisição crua; qualquer
      byte normalizado diferente é 401, então isto espelha `canonical.ts` ao pé
      da letra.
      """
  ```

- **Arquivos pequenos, uma responsabilidade.** Uma pasta por domínio (`crypto/`, `session/`, `resources/`,
  `transport/`). Nenhum arquivo acima de ~250 linhas.
- **`cli` e `api` importam só `diagnos`.** Se precisam de algo que o SDK não expõe, o SDK cresce — as cascas nunca
  reimplementam criptografia, assinatura ou lógica de retentativa.
- **Decisão pendente é `TODO(gustavo): ...`.** Sem `FIXME`, sem `HACK`.
- **Segredos nunca vivem em `bytearray` ou `bytes` Python.** Chaves de sessão, DEKs e chaves privadas vivem em
  `diagnos._secure.SecretBox` — memória Rust travada em página (`sdk/native`), zerada ao descartar. A única saída é
  `reveal()`, reservada para a exportação do auto-unseal no OpenBao.
- **`unsafe` em Rust fica confinado.** Vive só em `native/src/locked/` (memória e capabilities),
  `native/src/buffer.rs` e `native/src/process.rs` (rlimit/prctl) — os lugares que de fato tocam memória crua. Todo
  bloco `unsafe` carrega um comentário `SAFETY:` dizendo o invariante que o torna correto.
- **Rótulos de fio congelados nunca são renomeados.** Os rótulos HKDF/AAD `imgexam-*-v1` (`sdk/src/diagnos/crypto/`)
  e o id de chave de seal estático do OpenBao `imgexam-static-v1` (`api/deploy/`) são constantes criptográficas
  persistidas. Renomear qualquer um tornaria todo ciphertext armazenado, ou uma instalação existente do OpenBao,
  ilegível. Veja [`MIGRATING.pt-BR.md`](MIGRATING.pt-BR.md) para a explicação completa.

## Regra de documentação

Todo documento sai como `NOME.md` (inglês) ao lado de `NOME.pt-BR.md` (português do Brasil), com um seletor de
idioma logo abaixo do H1 apontando para o irmão. `scripts/check_docs.py` (parte do `make lint`) derruba o build
quando um documento não tem irmão, não tem seletor, ou tem um link relativo morto. `CHANGELOG.md` e os arquivos sob
`.github/` são isentos — veja a docstring desse script para a regra exata.

## Mudando o comportamento HTTP do SDK

Se sua mudança toca o que o `VaultTransport` manda para, ou lê de, o cofre, o contrato dele precisa mudar junto:

1. Adicione ou atualize a interação em `contracts/tests` (veja [`contracts/README.pt-BR.md`](contracts/README.pt-BR.md)
   para como).
2. Rode `make contract` para regerar `contracts/diagnos-sdk-diagnos-vault.json`.
3. Faça commit do arquivo regenerado no mesmo pull request.

O `make contract-check` da CI reprova um PR cujo comportamento do SDK mudou sem uma mudança de contrato
correspondente — ele compara o arquivo commitado contra uma rodada completa e nova, em vez de reescrevê-lo.

## Catraca de cobertura

`fail_under` no `pyproject.toml` da raiz (`[tool.coverage.report]`) é um piso, não uma meta: suba quando a cobertura
geral subir, nunca baixe para um pull request passar. `make cov` imprime o número combinado atual (cobertura de
ramos, os três pacotes).

## Estilo de commit

Commits seguem [Conventional Commits](https://www.conventionalcommits.org/): um tipo, um escopo opcional e um
resumo no imperativo — por exemplo `fix(sdk): correct clock skew handling`, `test(contracts): add a lock
interaction`, `docs: expand the OpenBao auto-unseal tradeoff`.

Todo commit precisa carregar um sign-off [DCO](https://developercertificate.org/). Use `git commit -s` (ou
acrescente `Signed-off-by: Seu Nome <voce@exemplo.com>` à mão) em todo commit; ele certifica que você tem o direito de enviar a mudança sob a licença do projeto.

## Lançamento de versões

Fora do escopo deste documento por enquanto. Resumindo: ainda não há um processo de release separado a seguir — a
versão de cada pacote vive no próprio `pyproject.toml` (`sdk/pyproject.toml`, `cli/pyproject.toml`,
`api/pyproject.toml`), e em tempo de execução `__version__` é lido dos metadados do pacote instalado, em vez de
fixado no código.

## Checklist de pull request

Antes de abrir um pull request:

- [ ] `make check` está verde localmente (lint, tipos, testes, checagem de contrato).
- [ ] Se o comportamento HTTP do SDK mudou, `contracts/diagnos-sdk-diagnos-vault.json` foi regenerado (`make
      contract`) e commitado.
- [ ] Toda documentação adicionada ou alterada existe em `NOME.md` e `NOME.pt-BR.md`, com estrutura e conteúdo
      equivalentes.
- [ ] Docstrings públicas novas ou alteradas (Python e Rust) carregam os dois parágrafos, `🇺🇸` e `🇧🇷`.
- [ ] Nenhum segredo, token ou credencial real foi commitado — inclusive em fixtures de teste e exemplos de deploy.
- [ ] Commits seguem Conventional Commits e têm sign-off (`git commit -s`).
