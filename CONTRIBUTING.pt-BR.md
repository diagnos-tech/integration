# Como contribuir

[English](CONTRIBUTING.md) · **Português (Brasil)**

Obrigado por considerar contribuir com o `diagnos` — a base, o SDK, a CLI, a API ou os wrappers. Este documento é o
guia prático: como preparar o projeto, o ciclo que você roda enquanto trabalha, o que a CI verifica e como reproduzir cada
checagem localmente, as convenções de código herdadas do histórico deste repositório, e a checklist de pull request.
Para os padrões de comportamento que valem para todo mundo, veja [`CODE_OF_CONDUCT.pt-BR.md`](CODE_OF_CONDUCT.pt-BR.md).
Para reportar uma vulnerabilidade, veja [`SECURITY.pt-BR.md`](SECURITY.pt-BR.md) em vez de abrir uma issue.

## Pré-requisitos

| Você precisa | Por quê |
|---|---|
| [uv](https://docs.astral.sh/uv/) | um venv para o pacote inteiro, com todo extra instalado editável |
| Python 3.11 – 3.13 | as três versões de CPython contra as quais a CI testa |
| [rustup](https://rustup.rs/) | só para construir o `apps/sdk/native` (o enclave de memória) a partir do fonte — ele instala o Rust que o `rust-toolchain.toml` fixa; os wheels do PyPI vêm prontos |

Você não precisa de Rust instalado para usar o `diagnos` a partir do PyPI; precisa dele para construir a partir de um
checkout, porque o `make sync` compila o `apps/sdk/native` para você.

O código é um pacote só, `src/diagnos`: a base (`_wrapper/`, `_entry.py`, `_extras.py`), o SDK no topo do pacote,
`cli/` e `api/`. Cada camada guarda o README, os testes e os recursos dela em `apps/<camada>/`, e os da base em
`wrappers/py/`.

## Primeira preparação

```sh
git clone https://github.com/diagnos-tech/integration && cd integration
make sync    # instala todo extra, editável, e constrói o enclave Rust
make check   # lint + tipos + testes + checagem de contrato — o que a CI roda
```

Se `make check` fica verde num clone recém-feito, seu ambiente bate com o da CI.

## O ciclo do dia a dia

```sh
make fmt        # formata e corrige automaticamente Python (ruff) e Rust (cargo fmt)
make test       # testes unitários: toda camada Python + o enclave Rust
make cov        # testes unitários com um relatório de cobertura combinado (htmlcov/)
make contract   # testes de consumidor Pact; regera contracts/*.json
```

Rode `make help` a qualquer momento para listar todo alvo com uma descrição de uma linha.

## O que a CI roda, e como reproduzir localmente

Pull requests miram a `develop` e entram como um commit só, via squash. A CI roda em todo pull request e o job `CI`
dela é o único check obrigatório; o Package roda quando a `main` anda, e decide se ela pode receber a tag.

| Workflow | Roda em | Responde | Equivalente local |
|---|---|---|---|
| `CI` (`.github/workflows/ci.yml`) | todo pull request, pushes na `main`, semanalmente na `develop` | Lint, `mypy --strict`, a doc, o contrato Pact e todo teste passam — no CPython 3.11 e 3.13, sem o piso de cobertura cair? Os próprios workflows são seguros (zizmor, actionlint)? | `make check`, `make cov`, `uvx zizmor .github/` |
| `CodeQL` (`.github/workflows/codeql.yml`) | todo pull request, semanalmente | A análise estática acha um bug de segurança no Python, no Rust ou nos workflows? | — |
| `Package` (`.github/workflows/package.yml`) | pushes na `main`, releases | Os sete wheels e o sdist constroem, cada wheel funciona instalado sozinho na própria plataforma — puro, depois com todo extra — e as duas imagens constroem? | `uv build`, depois `docker build --target api .` |
| `Release` (`.github/workflows/release.yml`) | tags `v*` na `main` | Assina e publica tudo; veja [Lançamento de versões](#lançamento-de-versões). | — |
| `Fuzz` (`.github/workflows/fuzz.yml`) | semanalmente | O libFuzzer derruba os parsers de AEAD, secretstream ou selo híbrido do enclave? | `make fuzz FUZZ_TARGET=<alvo>` |
| `Auto-merge` (`.github/workflows/auto-merge.yml`) | pull requests do Dependabot para a `develop` | Agenda o merge das atualizações minor e patch para quando a CI passar. | — |
| `Scorecard` (`.github/workflows/scorecard.yml`) | semanalmente | Como o repositório se sai nas práticas de cadeia de suprimentos. | — |

O `make check` roda `lint`, `types`, `test`, `contract-check` e `docs-check` — os passos dos jobs da CI, num comando
só — então um `make check` verde na sua máquina significa um pull request verde.

## Convenções de código

Estas regras valem para código (arquivos `.py` e `.rs`); moravam antes em `CONVENTIONS.md`, que este documento
substitui. Os arquivos em `.github/` são a exceção à regra bilíngue abaixo: os comentários deles são só em inglês.

- **Docstrings bilíngues.** Todo módulo, classe e função pública carrega uma docstring com um parágrafo em inglês
  prefixado `🇺🇸` seguido do parágrafo em português prefixado `🇧🇷`. Comentário em linha segue o mesmo par em linhas
  consecutivas. Comentário explica o **porquê** (a ameaça, o custo, a restrição do protocolo), nunca repete o
  código. Comentários de doc em Rust (`//!` de módulo, `///` de item) seguem a mesma regra à risca.
  `scripts/check_bilingual.py` (parte do `make lint`) derruba o build quando uma docstring ou comentário de doc está
  sem uma das bandeiras — em todo o `src/`, e nos testes para o módulo e todo teste, fixture, ajudante e classe de
  nível de cima.

  ```python no-run
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
  `transport/`); um módulo que passa de uma responsabilidade vira pacote (`models/`, `resources/_documents/`). Mire em
  ~250 linhas. `scripts/check_file_size.py` (parte do `make lint`) derruba o build acima de 300 linhas em fonte e 500
  em teste (o módulo `#[cfg(test)]` embutido num arquivo Rust não conta).
- **`diagnos.cli` e `diagnos.api` importam só `diagnos`.** Se precisam de algo que o SDK não expõe, o SDK cresce — as
  cascas nunca reimplementam criptografia, assinatura ou lógica de retentativa.
- **A base não precisa de nada além da biblioteca padrão.** `diagnos._wrapper`, `_entry`, `_extras` e o topo do
  `diagnos/__init__.py` rodam só com o `pip install diagnos`: nunca importam o SDK, a CLI ou a API, e um nome público
  novo do SDK entra nas duas listas do `diagnos/__init__.py` (os imports de `TYPE_CHECKING` e o `_SDK`). Os quatro
  comandos da base são um contrato compartilhado por todo wrapper de linguagem (`wrappers/contract.json`) — mude-o
  lá primeiro.
- **Extras continuam simples.** Todo `Requires-Dist` de um extra é um marcador `extra == "…"` simples, sobre uma
  distribuição que o `wrappers/py/tests/test_extras.py` permite; uma nova é uma mudança revisada nessa lista.
- **Decisão pendente é `TODO(gustavo): ...`.** Sem `FIXME`, sem `HACK`.
- **Segredos nunca vivem em `bytearray` ou `bytes` Python.** Chaves de sessão, DEKs e chaves privadas vivem em
  `diagnos._secure.SecretBox` — memória Rust travada em página (`apps/sdk/native`), zerada ao descartar. A única saída é
  `reveal()`, reservada para a exportação do auto-unseal no OpenBao.
- **`unsafe` em Rust fica confinado.** Vive só em `native/src/locked/` (memória e capabilities),
  `native/src/buffer.rs` e `native/src/process.rs` (rlimit/prctl) — os lugares que de fato tocam memória crua. Todo
  bloco `unsafe` carrega um comentário `SAFETY:` dizendo o invariante que o torna correto.
- **Rótulos de fio congelados nunca são renomeados.** Os rótulos HKDF/AAD `imgexam-*-v1` (`src/diagnos/crypto/`)
  e o id de chave de seal estático do OpenBao `imgexam-static-v1` (`apps/api/deploy/`) são constantes criptográficas
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
ramos, o pacote inteiro).

Para olhar uma área, mantenha a fonte no nível do pacote e leia as linhas dela: `pytest apps/sdk/tests --cov=diagnos
--cov-report=term-missing`. Uma fonte pontuada como `--cov=diagnos.crypto` faz o coverage importar o pacote
`diagnos` para localizá-lo e depois tirá-lo de `sys.modules`; a extensão Rust não pode ser inicializada duas vezes,
então ela mantém o primeiro `CryptoError` como base do `SecureError` enquanto o `diagnos.errors` é recriado — e todo
teste de "chave errada precisa levantar `CryptoError`" falha. É a ferramenta de medição, não o enclave.

## Estilo de commit

Commits seguem [Conventional Commits](https://www.conventionalcommits.org/): um tipo, um escopo opcional e um
resumo no imperativo — por exemplo `fix(sdk): correct clock skew handling`, `test(contracts): add a lock
interaction`, `docs: expand the OpenBao auto-unseal tradeoff`.

Todo commit precisa carregar um sign-off [DCO](https://developercertificate.org/). Use `git commit -s` (ou
acrescente `Signed-off-by: Seu Nome <voce@exemplo.com>` à mão) em todo commit; ele certifica que você tem o direito de enviar a mudança sob a licença do projeto.

## Lançamento de versões

A `develop` é onde o trabalho entra, um commit por pull request via squash; a `main` só anda para a frente, até um
commit que já está na `develop`. Nenhuma das duas recebe merge commits, e todo commit que entra nelas é assinado: o
GitHub assina os merges via squash, com o autor do pull request como autor do commit. O `diagnos` e as duas imagens dele são
lançados juntos, sob uma versão só, pelo `.github/workflows/release.yml`:

1. Num pull request para a `develop`, ponha a mesma versão no `pyproject.toml` e no `apps/sdk/native/Cargo.toml`,
   atualize os dois lockfiles (`uv lock` e `cargo update --workspace --manifest-path apps/sdk/native/Cargo.toml`), e
   dê à versão uma data no `CHANGELOG.md` no lugar de `Unreleased`. O `python3 scripts/release_version.py` diz se
   eles concordam.
2. Avance a `main` até esse commit: `git fetch origin && git push origin origin/develop:main`. Um fast-forward, nunca
   um merge: o push falha se a `main` tiver algo que a `develop` não tem. Ele roda o **Package** — toda distribuição
   construída, cada wheel experimentado na própria plataforma, o sdist reconstruído e as duas imagens construídas — e
   não publica nada.
3. Com o Package verde, marque esse commit com a tag e envie a tag: `git tag -s v0.1.0 origin/main -m "diagnos 0.1.0"
   && git push origin v0.1.0` (`-a` no lugar de `-s` se você não tiver chave de assinatura). O **Release** roda o
   Package de novo, assina todo arquivo com o cosign e atesta a proveniência dele, envia e assina as duas imagens,
   espera um mantenedor aprovar o ambiente `pypi`, publica no PyPI e cria o release no GitHub com todo arquivo,
   bundle, a proveniência, o SBOM e os comandos que os verificam.

Uma versão no PyPI nunca pode ser enviada duas vezes, e por isso o Package roda na `main` antes da tag. A publicação
usa o [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) do PyPI e a assinatura sem chave do Sigstore:
não há token nem chave para guardar ou trocar — e um token de API não é suportado de propósito, porque desligaria em
silêncio as atestações PEP 740. O PyPI confia no `release.yml` deste repositório, rodando no ambiente `pypi`;
renomear qualquer um dos dois quebra a publicação até o trusted publisher do PyPI ser ajustado. Em tempo de
execução, a `__version__` é lida dos metadados do pacote instalado em vez de fixa no código.

As dependências se atualizam sozinhas: o Dependabot abre pull requests agrupados para a `develop` uma vez por mês, as
atualizações minor e patch entram sozinhas quando a CI passa, e as major esperam revisão. Elas chegam à `main` com o
próximo release.

Um release candidate ensaia tudo de verdade: `0.2.0rc1` no `pyproject.toml`, `0.2.0-rc.1` no `Cargo.toml` (a guarda lê
os dois como uma versão só), uma seção `## [0.2.0rc1]` no `CHANGELOG.md`, e a tag `v0.2.0rc1`. O `pip` só instala um
pré-release quando pedido pela versão ou com `--pre`.

### Configurações do repositório

O que código não consegue configurar, um admin do repositório faz uma vez — nesta ordem, para o PyPI nunca confiar
num ambiente ou numa tag que qualquer um pudesse usar:

1. **Ambientes**: `release` e `pypi`, cada um limitado a tags `v*`, com um revisor obrigatório no `pypi` (e o
   *Prevent self-review* desligado enquanto houver um mantenedor só).
2. **Pull requests** (Settings → General): permita só **squash merging** — sem merge commits, sem rebase merging — e
   ligue *Allow auto-merge* (o Dependabot precisa) e *Automatically delete head branches*.
3. **Rulesets**, sem lista de bypass salvo onde um passo abaixo nomeia uma:
   - `develop`: exija pull request, o check **CI** e histórico linear; bloqueie force push e exclusão. Exija uma
     aprovação e revisão de code owner assim que houver dois mantenedores.
   - `main`: exija histórico linear; bloqueie force push e exclusão; restrinja atualizações, com *Repository admin*
     como único bypass, para só mantenedores a avançarem. Sem exigir pull request: a `main` nunca recebe merge.
   - tags `v*`: só mantenedores as criam (*Restrict creations*, com bypass só para admins), e ninguém as move nem
     apaga (*Restrict updates* e *Restrict deletions*, sem bypass — um segundo ruleset).
4. **Actions**: um `GITHUB_TOKEN` só de leitura, e o Actions sem permissão para criar ou aprovar pull requests.
   **Code security**: deixe o *default setup* do CodeQL desligado — o `codeql.yml` é o setup avançado, e os dois não
   convivem. **Releases**: imutabilidade ligada.
5. **PyPI**: um trusted publisher pendente para `diagnos` — dono `diagnos-tech`, repositório `integration`, workflow
   `release.yml`, ambiente `pypi` — 2FA para todo dono, e um segundo dono assim que houver. Nunca um token de API.
6. **GHCR**, só no primeiro release: a execução espera aprovação antes do `pypi`, com as duas imagens já enviadas e
   assinadas. Deixe `diagnos` e `diagnos-api` públicos e dê acesso de escrita só a este repositório, *depois* aprove
   — o `diagnos setup api` baixa a imagem assim que a versão chega ao PyPI.

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
