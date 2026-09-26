"""🇺🇸 `--help` on every command/subcommand, and the "missing required argument" contract.

Two behaviours the rest of `apps/cli/tests` never checks directly: every
`--help` invocation must exit `0` and print bilingual text (the actual help
strings baked into each `typer.Option`/`typer.Argument`/`app.command(help=...)`
call), and a missing required argument or option must exit `2` with a usage
error — never a traceback, and never exit `1` (which would look like a
runtime failure instead of a call-site mistake). This file also cross-checks
a handful of `apps/cli/README.md`'s documented options against the real
`--help` output, so a flag silently dropped from a command breaks a test
instead of only the docs.

🇧🇷 `--help` em todo comando/subcomando, e o contrato de "argumento
obrigatório ausente".

Duas coisas que o resto de `apps/cli/tests` nunca checa direto: toda chamada de
`--help` precisa sair com `0` e imprimir texto bilíngue (as strings de help de
verdade, dentro de cada `typer.Option`/`typer.Argument`/`app.command(help=...)`),
e um argumento ou opção obrigatório ausente precisa sair com `2` e um erro de
uso — nunca um traceback, e nunca `1` (que pareceria uma falha em tempo de
execução, não um erro de chamada). Este arquivo também confere um punhado das
opções documentadas em `apps/cli/README.md` contra a saída real de `--help`,
para uma flag removida em silêncio de um comando quebrar um teste, não só a
documentação.
"""

from __future__ import annotations

import pytest
from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import FakeDiagnos

# 🇺🇸 Every command path this package registers, root first — used to drive
# both the `--help` sweep and the bilingual-text assertion below.
# 🇧🇷 Todo caminho de comando que este pacote registra, raiz primeiro — usado
# tanto na varredura de `--help` quanto na asserção de texto bilíngue abaixo.
ALL_COMMAND_PATHS: list[list[str]] = [
    [],
    ["login"],
    ["status"],
    ["groups"],
    ["session"],
    ["session", "lock"],
    ["patients"],
    ["patients", "list"],
    ["patients", "get"],
    ["patients", "create"],
    ["patients", "update"],
    ["patients", "archive"],
    ["patients", "unarchive"],
    ["patients", "delete"],
    ["patients", "restore"],
    ["exams"],
    ["exams", "list"],
    ["exams", "get"],
    ["exams", "create"],
    ["exams", "update"],
    ["exams", "archive"],
    ["exams", "unarchive"],
    ["exams", "delete"],
    ["exams", "restore"],
    ["files"],
    ["files", "list"],
    ["files", "upload"],
    ["files", "mkdir"],
    ["files", "download"],
    ["files", "get"],
]


@pytest.mark.parametrize("command_path", ALL_COMMAND_PATHS, ids=lambda path: " ".join(path) or "root")
def test_help_exits_zero_and_is_bilingual(runner: CliRunner, command_path: list[str]) -> None:
    """🇺🇸 `<command> --help` exits `0` and its help text carries the `·` bilingual separator.

    Every `help=` string in `apps/cli/src/diagnos_cli` is written as
    `"English · Português"`; asserting on the separator (rather than
    hard-coding one language's words here) is what catches *any* command
    whose help lost its Portuguese half, not just the ones this test
    happens to quote.

    🇧🇷 `<comando> --help` sai com `0` e seu texto de ajuda carrega o
    separador bilíngue `·`.

    Toda string `help=` em `apps/cli/src/diagnos_cli` é escrita como
    `"Inglês · Português"`; checar o separador (em vez de fixar as palavras
    de uma língua aqui) é o que pega *qualquer* comando cuja ajuda perdeu a
    metade em português, não só os que este teste por acaso cita.
    """
    result = runner.invoke(typer_app, [*command_path, "--help"])
    assert result.exit_code == 0
    assert "Traceback" not in result.output
    assert "·" in result.output


def test_root_help_lists_the_global_options(runner: CliRunner) -> None:
    """🇺🇸 The root `--help` documents every global option the README's table promises.

    🇧🇷 O `--help` da raiz documenta toda opção global que a tabela do README promete.
    """
    result = runner.invoke(typer_app, ["--help"])
    assert result.exit_code == 0
    for flag in ("--json", "--quiet", "--vault-url", "--token", "--no-color", "--version"):
        assert flag in result.output


def test_no_arguments_at_all_prints_help_and_succeeds(runner: CliRunner) -> None:
    """🇺🇸 Running `diagnos` bare prints the full bilingual help, ends with where to start, and exits `0`.

    Someone typing `diagnos` alone is finding their way, not making a
    mistake — like `gh`, `docker` or `kubectl`, it succeeds.

    🇧🇷 Rodar `diagnos` sozinho imprime a ajuda bilíngue inteira, termina com por onde começar, e sai com `0`.

    Quem digita `diagnos` sozinho está se orientando, não errando — como
    `gh`, `docker` ou `kubectl`, termina com sucesso.
    """
    result = runner.invoke(typer_app, [])
    assert result.exit_code == 0
    assert "diagnos login" in result.output
    assert "Traceback" not in result.output
    assert "·" in result.output
    assert "Usage" in result.output


@pytest.mark.parametrize(
    "argv",
    [
        ["patients", "get"],
        ["patients", "update", "pat_1"],
        ["patients", "archive"],
        ["exams", "get"],
        ["exams", "create", "--group", "sg1"],
        ["exams", "update", "exam_1"],
        ["files", "upload", "--group", "sg1"],
        ["files", "mkdir", "--group", "sg1"],
        ["files", "download"],
    ],
    ids=lambda argv: " ".join(argv),
)
def test_missing_required_argument_exits_2_with_a_usage_error(
    runner: CliRunner, patched_build_client: FakeDiagnos, argv: list[str]
) -> None:
    """🇺🇸 A missing required argument/option is a usage error: exit `2`, no traceback, never `build_client`.

    Click's own contract is exit `2` for `UsageError`; this happens to be
    the same code `exit_codes.EXIT_CONFIG` uses for a *different* kind of
    mistake (a bad token/env var). Locking both to `2` here is what a
    script's `case "$code" in 2) ...` branch actually depends on: it never
    has to tell "wrong flags" from "wrong environment" apart.

    🇧🇷 Um argumento/opção obrigatório ausente é um erro de uso: sai com
    `2`, sem traceback, nunca chega a `build_client`.

    O próprio contrato do click é sair com `2` para `UsageError`; por
    coincidência é o mesmo código que `exit_codes.EXIT_CONFIG` usa para um
    tipo *diferente* de erro (token/variável de ambiente ruins). Fixar os
    dois em `2` aqui é do que um `case "$code" in 2) ...` de script depende
    de verdade: nunca precisa distinguir "flags erradas" de "ambiente
    errado".
    """
    result = runner.invoke(typer_app, argv)
    assert result.exit_code == 2
    assert "Traceback" not in result.output
    # 🇺🇸 Click rejects the call while parsing options, before the command
    # body — and therefore `context.build_client` — ever runs.
    # 🇧🇷 O click rejeita a chamada durante o parse das opções, antes do
    # corpo do comando — e portanto `context.build_client` — sequer rodar.
    assert not patched_build_client.patients.calls
    assert not patched_build_client.exams.calls
    assert not patched_build_client.drives.calls


@pytest.mark.parametrize(
    ("command", "expected_options"),
    [
        (["patients", "list"], ["--group", "--include-deleted", "--limit", "--cursor", "--all", "--summary"]),
        (["patients", "create"], ["--group", "--file", "--legal-name", "--display-name", "--birth-date", "--tag"]),
        (["patients", "update"], ["--file", "--tag", "--expect-version"]),
        (["patients", "delete"], ["--yes"]),
        (["exams", "create"], ["--patient", "--group", "--file", "--title", "--modality", "--exam-date"]),
        (["exams", "update"], ["--file", "--expect-version"]),
        (["files", "list"], ["--group", "--folder", "--exam", "--include-pending", "--limit", "--cursor", "--all"]),
        (["files", "upload"], ["--group", "--exam", "--folder"]),
        (["files", "mkdir"], ["--group", "--parent"]),
        (["files", "download"], ["--output"]),
        (["login"], ["--auto-unseal"]),
        (["status"], ["--check"]),
    ],
    ids=lambda value: " ".join(value) if isinstance(value, list) else value,
)
def test_help_matches_the_readme_option_table(
    runner: CliRunner, command: list[str], expected_options: list[str]
) -> None:
    """🇺🇸 Every option `apps/cli/README.md`'s command table lists for `command` still exists in `--help`.

    A flag quietly removed (or renamed) from a command's `typer.Option`
    would leave the README wrong and every other test in this suite
    unaware — none of them enumerate options, they only pass the ones they
    already know about.

    🇧🇷 Toda opção que a tabela de comandos do `apps/cli/README.md` lista para
    `command` ainda existe no `--help`.

    Uma flag removida (ou renomeada) em silêncio de um `typer.Option` de
    comando deixaria o README errado e todo outro teste desta suíte sem
    perceber — nenhum deles enumera opções, só passam as que já conhecem.
    """
    result = runner.invoke(typer_app, [*command, "--help"])
    assert result.exit_code == 0
    for option in expected_options:
        assert option in result.output, f"{option!r} missing from {' '.join(command)} --help"
