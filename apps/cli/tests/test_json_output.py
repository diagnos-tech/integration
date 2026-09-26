"""🇺🇸 `--json` is exactly one JSON document on `stdout`; `--quiet`/`--no-color` are checked the same rigorous way.

`click.testing.CliRunner.invoke`'s result exposes `stdout` and `stderr`
separately (`result.output` mixes them, the way a real terminal would) —
every `--json` assertion below reads `result.stdout` alone, so a spinner or
an enrollment panel accidentally printed to the wrong console would fail the
test even though `result.output` might still "look" fine. `--quiet` and
`--no-color` get the same treatment: compared against the same command run
without the flag, not asserted in isolation, so a regression that makes them
no-ops is caught.

🇧🇷 `--json` é exatamente um documento JSON na `stdout`; `--quiet`/`--no-color`
são checados com o mesmo rigor.

O resultado de `click.testing.CliRunner.invoke` expõe `stdout` e `stderr`
separados (`result.output` mistura os dois, como um terminal de verdade
faria) — toda asserção de `--json` abaixo lê só `result.stdout`, então um
spinner ou um painel de enrollment impresso por engano no console errado
derrubaria o teste mesmo que `result.output` ainda "parecesse" certo.
`--quiet` e `--no-color` recebem o mesmo tratamento: comparados contra o
mesmo comando rodado sem a flag, nunca isolados, para uma regressão que os
torne inofensivos ser pega.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import EXAM_INDEX, PATIENT_INDEX, FakeDiagnos

# 🇺🇸 One argv per command that supports `--json`, prefixed with it by the
# test below — covers every mutation `test_patients.py`/`test_exams.py`
# happen not to already assert `--json` on, so the "exactly one document,
# nothing else on stdout" contract is checked everywhere, not just where a
# happy-path test already reached for `json.loads`.
# 🇧🇷 Um argv por comando que suporta `--json`, prefixado com a flag pelo
# teste abaixo — cobre toda mutação que `test_patients.py`/`test_exams.py`
# não chegam a checar com `--json`, para o contrato "exatamente um
# documento, nada mais na stdout" ser checado em todo lugar, não só onde um
# teste de caminho feliz já chamava `json.loads`.
JSON_COMMANDS: list[list[str]] = [
    ["login"],
    ["status"],
    ["status", "--check"],
    ["groups"],
    ["patients", "list"],
    ["patients", "get", PATIENT_INDEX.document_id],
    ["patients", "create", "--group", "sg1", "--legal-name", "Ana"],
    ["patients", "archive", PATIENT_INDEX.document_id],
    ["patients", "unarchive", PATIENT_INDEX.document_id],
    ["patients", "delete", PATIENT_INDEX.document_id, "--yes"],
    ["patients", "restore", PATIENT_INDEX.document_id],
    ["exams", "list"],
    ["exams", "get", EXAM_INDEX.document_id],
    ["exams", "create", "--patient", "pat_1", "--group", "sg1", "--title", "CT"],
    ["exams", "archive", EXAM_INDEX.document_id],
    ["exams", "unarchive", EXAM_INDEX.document_id],
    ["exams", "delete", EXAM_INDEX.document_id, "--yes"],
    ["exams", "restore", EXAM_INDEX.document_id],
    ["files", "list"],
    ["files", "get", "node_1"],
    ["files", "mkdir", "Series 1", "--group", "sg1"],
]


@pytest.mark.parametrize("argv", JSON_COMMANDS, ids=lambda argv: " ".join(argv))
def test_json_is_exactly_one_document_on_stdout(
    runner: CliRunner, patched_build_client: FakeDiagnos, argv: list[str]
) -> None:
    """🇺🇸 `stdout` parses as one JSON value, with no leftover bytes before or after it.

    `json.JSONDecoder.raw_decode` (not `json.loads`) is what actually proves
    "exactly one document": `loads` alone would also pass for `"{}garbage"`
    parsed leniently in some corner cases, whereas `raw_decode` reports
    precisely how many characters the document consumed, so trailing noise
    (a stray `print`, a second document) is caught by comparing that to the
    stream's full length.

    🇧🇷 `stdout` interpreta como um único valor JSON, sem sobra de bytes
    antes ou depois dele.

    `json.JSONDecoder.raw_decode` (não `json.loads`) é o que prova de fato
    "exatamente um documento": só `loads` também passaria para
    `"{}garbage"` em algum canto leniente, enquanto `raw_decode` informa
    quantos caracteres o documento consumiu, então ruído sobrando (um
    `print` perdido, um segundo documento) é pego comparando isso com o
    tamanho total do stream.
    """
    result = runner.invoke(typer_app, ["--json", *argv])
    assert result.exit_code == 0
    stdout = result.stdout
    assert stdout.endswith("\n")
    value, end = json.JSONDecoder().raw_decode(stdout)
    assert stdout[end:] == "\n"
    assert isinstance(value, (dict, list))


def test_json_upload_is_exactly_one_document_even_with_the_progress_bar_active(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `files upload --json` without `--quiet` still drives a `rich.progress.Progress` bar — on `stderr` only.

    🇧🇷 `files upload --json` sem `--quiet` ainda conduz uma barra
    `rich.progress.Progress` — só na `stderr`.
    """
    source = tmp_path / "scan.dcm"
    source.write_bytes(b"x")
    result = runner.invoke(typer_app, ["--json", "files", "upload", "--group", "sg1", str(source)])
    assert result.exit_code == 0
    value, end = json.JSONDecoder().raw_decode(result.stdout)
    assert result.stdout[end:] == "\n"
    assert value["items"][0]["node"]["node_id"] == "node_1"


def test_quiet_suppresses_the_downloaded_confirmation_line(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `--quiet` on `download` drops the "Saved · Salvo" line too, not only the transient spinner.

    Without `--quiet` the command still prints a human confirmation after
    the (invisible, transient) spinner stops; `--quiet` suppresses that
    line as well — comparing the two runs is what proves `--quiet` changes
    anything at all, since the spinner itself never lands in captured
    output either way (a `rich` status is transient and leaves no trace on
    `.stop()`).

    🇧🇷 `--quiet` no `download` também derruba a linha "Saved · Salvo", não
    só o spinner transitório.

    Sem `--quiet` o comando ainda imprime uma confirmação humana depois do
    spinner (invisível, transitório) parar; `--quiet` também suprime essa
    linha — comparar as duas execuções é o que prova que `--quiet` muda
    alguma coisa, já que o próprio spinner nunca aparece na saída capturada
    de qualquer jeito (um status `rich` é transitório e não deixa rastro no
    `.stop()`).
    """
    loud = runner.invoke(typer_app, ["files", "download", "node_1", "-o", str(tmp_path / "loud.dcm")])
    quiet = runner.invoke(typer_app, ["--quiet", "files", "download", "node_1", "-o", str(tmp_path / "quiet.dcm")])

    assert loud.exit_code == 0
    assert quiet.exit_code == 0
    assert "Saved" in loud.output
    assert loud.output.strip() != ""
    assert quiet.output == ""


def test_no_color_strips_the_color_codes_readme_promises(
    runner: CliRunner, patched_build_client: FakeDiagnos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 With color forced on, `--no-color` removes the SGR color numbers from every styled line.

    `FORCE_COLOR` makes `rich` treat the captured buffer as a terminal
    (`Console.is_terminal` reads it before ever checking `isatty()`), which
    is required here: `CliRunner` otherwise captures to a plain
    `io.StringIO`, and `rich` already emits no escape codes at all against a
    non-terminal file — a run without `FORCE_COLOR` would "pass" this
    assertion for a command that never even tried to color its output.

    🇧🇷 Com a cor forçada, `--no-color` remove os números de cor SGR de toda
    linha estilizada.

    `FORCE_COLOR` faz o `rich` tratar o buffer capturado como um terminal
    (`Console.is_terminal` lê isto antes mesmo de checar `isatty()`), o que é
    necessário aqui: sem isso o `CliRunner` captura para um `io.StringIO`
    simples, e o `rich` já não emite código de escape nenhum contra um
    arquivo que não é terminal — uma execução sem `FORCE_COLOR` "passaria"
    esta asserção para um comando que nunca sequer tentou colorir a saída.
    """
    monkeypatch.setenv("FORCE_COLOR", "1")
    colored = runner.invoke(typer_app, ["login"], color=True)
    plain = runner.invoke(typer_app, ["--no-color", "login"], color=True)

    assert colored.exit_code == 0
    assert plain.exit_code == 0
    # 🇺🇸 `32` is the green SGR number `[bold green]Enrolled...[/bold green]`
    # renders as; it must appear with color and never with `--no-color`.
    # 🇧🇷 `32` é o número SGR do verde que `[bold green]Enrolled...[/bold green]`
    # renderiza; precisa aparecer com cor e nunca com `--no-color`.
    assert "\x1b[1;32m" in colored.output
    assert "\x1b[1;32m" not in plain.output
    assert "32m" not in plain.output


def test_no_color_removes_every_ansi_escape_sequence(
    runner: CliRunner, patched_build_client: FakeDiagnos, monkeypatch: pytest.MonkeyPatch
) -> None:
    r"""🇺🇸 The stronger reading of `--no-color` — zero ANSI escapes of any kind — does not hold today.

    `rich.console.Console(no_color=True)` strips color but leaves bold/dim
    style codes alone, and several panels/messages use `[bold]`/`[dim]` with
    no color at all (`render/_shared.py`'s `record_panel`, `groups`'
    "no security groups" line). A script that greps `--no-color` output for
    a bare absence of `\\x1b` (rather than specifically color numbers) would
    still see escape sequences.

    🇧🇷 A leitura mais forte de `--no-color` — zero escapes ANSI de qualquer
    tipo — não se sustenta hoje.

    `rich.console.Console(no_color=True)` remove cor mas deixa os códigos de
    estilo bold/dim intactos, e vários painéis/mensagens usam
    `[bold]`/`[dim]` sem cor nenhuma (`record_panel` de `render/_shared.py`,
    a linha "nenhum security group" de `groups`). Um script que faz grep na
    saída de `--no-color` por ausência total de `\\x1b` (em vez de
    especificamente números de cor) ainda veria sequências de escape.
    """
    monkeypatch.setenv("FORCE_COLOR", "1")
    result = runner.invoke(typer_app, ["--no-color", "login"], color=True)

    assert result.exit_code == 0
    assert "\x1b[" not in result.output
