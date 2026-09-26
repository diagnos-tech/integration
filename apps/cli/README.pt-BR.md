# diagnos-cli

[English](README.md) · **Português (Brasil)**

A linha de comando `diagnos` — o cofre diagnos zero-knowledge, do seu terminal, construída sobre o SDK
[`diagnos`](https://github.com/diagnos-tech/integration/blob/develop/apps/sdk/README.pt-BR.md). Todo byte de
criptografia, assinatura e lógica de retentativa mora no SDK; este pacote só interpreta argumentos e renderiza o que o
SDK devolve — tabelas para pessoas, JSON para scripts, códigos de saída estáveis para os dois.

> [!NOTE]
> **Ainda não está no PyPI.** O `pipx install diagnos-cli` abaixo é o comando de instalação pretendido e permanente —
> mas, até o primeiro release, instale do código-fonte (construir o SDK exige um [toolchain Rust](https://rustup.rs/);
> a `cli` depende do SDK `diagnos`, ainda não publicado, então os dois vêm do git num comando só):
> ```sh
> pipx install "diagnos-cli @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/cli" \
>   --preinstall "diagnos @ git+https://github.com/diagnos-tech/integration@develop#subdirectory=apps/sdk"
> ```
> Vindo do `imgexam-cli`? As versões recomeçam em `0.1.0` sob o nome novo — leia o
> [MIGRATING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/MIGRATING.pt-BR.md) antes de atualizar.

## Instalação

```sh
pipx install diagnos-cli
pipx install "diagnos-cli[openbao]"   # com auto-unseal via OpenBao, para cron e servidores
export DIAGNOS_API_TOKEN="apikey-…"   # emitido por um admin do workspace
```

`--token` em qualquer comando sobrescreve o ambiente naquela invocação, e nunca é ecoado — nem no `--help`, nem na
saída, nem no `--json`.

## Uma primeira execução

```sh
diagnos login                                      # imprime um link e um código; um admin aprova
diagnos patients list --group sg_oncology --summary
diagnos files upload --group sg_oncology --exam EXAM_ID scans/*.dcm
diagnos --json exams get EXAM_ID | jq .record.report_html
```

Cada invocação é um processo próprio, e **a CLI nunca grava uma sessão em disco**: sem OpenBao, o comando seguinte faz
enrollment de novo, com link e código novos. É de propósito — um script que roda sem ninguém olhando configura o
auto-unseal com OpenBao, como o guia da CLI mostra.

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
uv run --package diagnos-cli pytest apps/cli/tests -q
uv run ruff check apps/cli && uv run ruff format --check apps/cli
uv run mypy apps/cli/src
```

Os exemplos de um comando moram ao lado dele, no `epilog` (`diagnos_cli.examples`): aparecem no fim do `--help` e na
referência gerada, e o `make docs-check` falha se os dois divergirem. Veja o
[CONTRIBUTING.pt-BR.md](https://github.com/diagnos-tech/integration/blob/develop/CONTRIBUTING.pt-BR.md) para a regra de
docstring bilíngue e a fronteira "a `cli` só importa `diagnos`".
