# diagnos · linha de comando

[English](README.md) · **Português (Brasil)**

A linha de comando `diagnos` — o cofre diagnos zero-knowledge, do seu terminal, construída sobre o SDK
[`diagnos`](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.pt-BR.md). Todo byte de
criptografia, assinatura e lógica de retentativa mora no SDK; este pacote só interpreta argumentos e renderiza o que o
SDK devolve — tabelas para pessoas, JSON para scripts, códigos de saída estáveis para os dois. Ela é o extra `cli` do
pacote único `diagnos`; o código dela mora em `src/diagnos/cli`.

> [!NOTE]
> **Até a `0.1.0` estar no PyPI**, instale a partir do repositório (construir o SDK exige um
> [toolchain Rust](https://rustup.rs/)):
> ```sh
> uv tool install "diagnos[cli] @ git+https://github.com/diagnos-tech/integration@develop"
> ```
> Vindo do `imgexam-cli` ou do `diagnos-cli`? Leia o
> [MIGRATING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.pt-BR.md) antes de atualizar.

## Instalação

```sh
uv tool install "diagnos[cli]"            # ou: pipx install "diagnos[cli]"
uv tool install "diagnos[cli,openbao]"    # com auto-unseal via OpenBao, para cron e servidores
export DIAGNOS_API_TOKEN="apikey-…"       # emitido por um admin do workspace
```

Já tem a base (`pip install diagnos`)? O `diagnos setup cli` soma o resto a esse mesmo `diagnos`. Sem Python, a
imagem também funciona: `docker run --rm -e DIAGNOS_API_TOKEN ghcr.io/diagnos-tech/diagnos patients list`.

`--token` em qualquer comando sobrescreve o ambiente naquela invocação, e nunca é ecoado — nem no `--help`, nem na
saída, nem no `--json`.

## Uma primeira execução

```sh
diagnos login                                      # imprime um link e um código; um admin aprova
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology --exam EXAM_ID scans/*.dcm
diagnos --json exams get EXAM_ID | jq .record.report_html
diagnos logout                                     # revoga a sessão e apaga as chaves
```

O `login` mantém essa sessão para os comandos seguintes — sem link novo, sem código novo — até o `diagnos logout`.
Ela vive num único processo em segundo plano, o *agente de sessão*, na memória travada do SDK: **a CLI nunca grava
uma sessão em disco**. Sem `login`, cada comando faz enrollment por conta própria e a sessão morre com ele — um script
que roda sem ninguém olhando configura o auto-unseal com OpenBao, como o guia da CLI mostra.

## Guias

| | |
|---|---|
| [Guia da CLI](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/cli.pt-BR.md) | todo comando com exemplos reais, saída JSON, scripts e cron |
| [Referência da CLI](https://github.com/diagnos-tech/integration/blob/develop/docs/reference/cli.json) | todo comando e opção, gerados a partir do código — também `diagnos <comando> --help` |
| [Autenticação](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/authentication.pt-BR.md) | o token, o painel de enrollment, a aprovação |
| [Sessões](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/sessions.pt-BR.md#auto-unseal-com-openbao) | o auto-unseal com OpenBao, e o que ele troca |
| [Erros](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/errors.pt-BR.md#toda-exceção) | o código de saída de toda falha |
| [Configuração](https://github.com/diagnos-tech/integration/blob/develop/docs/guides/configuration.pt-BR.md) | toda variável de ambiente |

Limites conhecidos e as questões ainda em aberto do lado do cofre:
[Compatibilidade com o cofre](https://github.com/diagnos-tech/integration/blob/develop/docs/COMPATIBILITY.pt-BR.md).

## Desenvolvimento

```sh
make sync
uv run pytest apps/cli/tests -q
uv run ruff check src/diagnos/cli apps/cli && uv run ruff format --check src/diagnos/cli apps/cli
uv run mypy src
```

Os exemplos de um comando moram ao lado dele, no `epilog` (`diagnos.cli.examples`): aparecem no fim do `--help` e na
referência gerada, e o `make docs-check` falha se os dois divergirem. Veja o
[CONTRIBUTING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.pt-BR.md) para a regra de
docstring bilíngue e a fronteira "o `diagnos.cli` só importa `diagnos`".
