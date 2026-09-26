"""🇺🇸 What wins when two ways of saying the same thing disagree, and what the CLI deliberately never validates.

`--file` versus inline flags, `--all` versus `--cursor`, and a boolean pair
like `--auto-unseal`/`--no-auto-unseal` each have one documented or
`click`-given precedence rule; this file locks each one down end to end
(through the real Typer app, not by calling a helper function directly) so a
change to option wiring in `commands/*.py` breaks a test here before it
breaks a user's script. It also covers two rendering paths no fixed fake in
`conftest.py` ever exercises on its own: an empty page's "no results" line
and a non-empty `next_cursor` hint, both reached through a real command
invocation this time, not `render_index_table` called directly.

🇧🇷 O que vence quando duas formas de dizer a mesma coisa discordam, e o que
a CLI deliberadamente nunca valida.

`--file` contra flags inline, `--all` contra `--cursor`, e um par booleano
como `--auto-unseal`/`--no-auto-unseal` têm cada um uma regra de precedência
documentada ou dada pelo `click`; este arquivo tranca cada uma ponta a ponta
(pela app Typer de verdade, não chamando uma função auxiliar direto) para
uma mudança na fiação de opções em `commands/*.py` quebrar um teste aqui
antes de quebrar o script de alguém. Também cobre dois caminhos de
renderização que nenhum fake fixo de `conftest.py` exercita sozinho: a linha
"nenhum resultado" de uma página vazia e a dica de `next_cursor` não vazio,
desta vez alcançados por uma invocação de comando de verdade, não por
chamar `render_index_table` direto.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from diagnos import Page
from diagnos_cli import context as context_module
from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import DRIVE_NODE, PATIENT_ITEM, FakeDiagnos


def test_patients_create_file_wins_over_inline_flags_end_to_end(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `--file` together with `--legal-name` sends only the file's content to `Patients.create`.

    `test_inputs.py` proves this at the `load_record` level; this is the
    same rule through the real command, so a future `patients create` that
    (say) merges the two instead of choosing one would still be caught.

    🇧🇷 `--file` junto com `--legal-name` manda só o conteúdo do arquivo para
    `Patients.create`.

    `test_inputs.py` prova isto no nível de `load_record`; este é o mesmo
    controle pelo comando de verdade, para um futuro `patients create` que
    (digamos) misture os dois em vez de escolher um ainda ser pego.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({"legal_name": "From file"}), encoding="utf-8")

    result = runner.invoke(
        typer_app,
        ["patients", "create", "--group", "sg1", "--file", str(record_file), "--legal-name", "From flag"],
    )

    assert result.exit_code == 0
    _, kwargs = patched_build_client.patients.calls[-1]
    assert kwargs["record"] == {"legal_name": "From file"}


def test_exams_create_file_wins_over_inline_flags_end_to_end(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 The same `--file`-wins rule holds for `exams create`'s `--title`/`--modality`/`--exam-date`.

    🇧🇷 A mesma regra de `--file` vencer vale para `--title`/`--modality`/`--exam-date` de `exams create`.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({"title": "From file"}), encoding="utf-8")

    result = runner.invoke(
        typer_app,
        ["exams", "create", "--patient", "pat_1", "--group", "sg1", "--file", str(record_file), "--title", "Ignored"],
    )

    assert result.exit_code == 0
    _, kwargs = patched_build_client.exams.calls[-1]
    assert kwargs["record"] == {"title": "From file"}


def test_patients_list_all_flag_ignores_cursor(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `--all --cursor X` walks `iter_all` — `--cursor` is silently dropped, never reaches the SDK call.

    A conflict like this needs a *documented* winner: a script piping in
    `--cursor` from a previous run and adding `--all` later should not
    resume from the middle of the walk by accident.

    🇧🇷 `--all --cursor X` percorre `iter_all` — `--cursor` é descartado em
    silêncio, nunca chega à chamada do SDK.

    Um conflito como este precisa de um vencedor *documentado*: um script
    que encadeia `--cursor` de uma execução anterior e depois acrescenta
    `--all` não deveria retomar do meio do percurso por acidente.
    """
    result = runner.invoke(typer_app, ["patients", "list", "--all", "--cursor", "some_cursor"])

    assert result.exit_code == 0
    names = [name for name, _ in patched_build_client.patients.calls]
    assert names == ["iter_all"]
    _, kwargs = patched_build_client.patients.calls[-1]
    assert "cursor" not in kwargs


def test_files_list_all_flag_ignores_cursor(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 The same `--all`-over-`--cursor` precedence holds for `files list`.

    🇧🇷 A mesma precedência de `--all` sobre `--cursor` vale para `files list`.
    """
    result = runner.invoke(typer_app, ["files", "list", "--all", "--cursor", "some_cursor"])

    assert result.exit_code == 0
    names = [name for name, _ in patched_build_client.drives.calls]
    assert names == ["iter_all"]


def test_login_last_auto_unseal_flag_on_the_command_line_wins(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, fake_vault: FakeDiagnos
) -> None:
    """🇺🇸 `click`'s own rule for a `--flag/--no-flag` pair: whichever spelling comes last decides the value.

    Bypasses `patched_build_client` on purpose (it ignores every argument) to
    capture the actual `auto_unseal` value `login` passes through —
    `--auto-unseal --no-auto-unseal` and its reverse must disagree, or this
    "last one wins" precedence would not be locked down at all.

    🇧🇷 A própria regra do `click` para um par `--flag/--no-flag`: a grafia
    que vier por último decide o valor.

    Contorna `patched_build_client` de propósito (ele ignora todo argumento)
    para capturar o valor real de `auto_unseal` que `login` repassa —
    `--auto-unseal --no-auto-unseal` e o inverso precisam discordar, senão
    esta precedência de "o último vence" não estaria travada de jeito nenhum.
    """
    seen: list[bool | None] = []

    def _capturing_build_client(
        options: object, *, on_prompt: object = None, auto_unseal: bool | None = None
    ) -> object:
        """🇺🇸 Records `auto_unseal` and hands back the shared fake. 🇧🇷 Registra `auto_unseal` e devolve o fake."""
        seen.append(auto_unseal)
        return fake_vault

    monkeypatch.setattr(context_module, "build_client", _capturing_build_client)

    runner.invoke(typer_app, ["login", "--auto-unseal", "--no-auto-unseal"])
    runner.invoke(typer_app, ["login", "--no-auto-unseal", "--auto-unseal"])

    assert seen == [False, True]


def test_a_misspelled_record_field_is_forwarded_to_the_sdk_unvalidated(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `inputs.load_record` never checks field names — a typo reaches `Patients.create` verbatim.

    By design (`inputs.py`'s own docstring): field validation is the SDK's
    `coerce_record`'s job, done once, not duplicated here. This is the CLI
    boundary made explicit: a misspelled key is *not* caught client-side —
    `test_errors.py`'s `ValidationError` row covers what happens once the
    real SDK does reject it.

    🇧🇷 `inputs.load_record` nunca confere nomes de campo — um erro de
    digitação chega a `Patients.create` do jeito que veio.

    De propósito (a própria docstring de `inputs.py`): validar campo é
    trabalho do `coerce_record` do SDK, feito uma vez só, não duplicado
    aqui. Este é o limite da CLI tornado explícito: uma chave com erro de
    digitação *não* é pega do lado do cliente — a linha de `ValidationError`
    de `test_errors.py` cobre o que acontece quando o SDK de verdade a
    rejeita.
    """
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({"legal_name": "Ana", "leagl_nmae": "typo"}), encoding="utf-8")

    result = runner.invoke(typer_app, ["patients", "create", "--group", "sg1", "--file", str(record_file)])

    assert result.exit_code == 0
    _, kwargs = patched_build_client.patients.calls[-1]
    assert kwargs["record"] == {"legal_name": "Ana", "leagl_nmae": "typo"}


def test_patients_list_shows_no_results_message_through_the_real_command(
    runner: CliRunner, patched_build_client: FakeDiagnos
) -> None:
    """🇺🇸 An empty page from the (patched) SDK reaches the same "no results" line `test_render.py` checks in isolation.

    🇧🇷 Uma página vazia da chamada (com patch) do SDK chega na mesma linha
    "nenhum resultado" que `test_render.py` confere isolado.
    """
    patched_build_client.patients.list = lambda **kwargs: Page(items=[], next_cursor=None)  # type: ignore[method-assign]

    table = runner.invoke(typer_app, ["patients", "list"])
    as_json = runner.invoke(typer_app, ["--json", "patients", "list"])

    assert table.exit_code == 0
    assert "No results · Nenhum resultado" in table.output
    assert json.loads(as_json.output)["items"] == []


def test_files_list_shows_the_next_cursor_hint_through_the_real_command(
    runner: CliRunner, patched_build_client: FakeDiagnos
) -> None:
    """🇺🇸 A non-empty `next_cursor` from the (patched) SDK call reaches the resume hint, end to end.

    🇧🇷 Um `next_cursor` não vazio da chamada (com patch) do SDK chega na dica de retomar, ponta a ponta.
    """
    patched_build_client.drives.list = lambda **kwargs: Page(  # type: ignore[method-assign]
        items=[DRIVE_NODE], next_cursor="cursor_xyz"
    )

    table = runner.invoke(typer_app, ["files", "list"])
    as_json = runner.invoke(typer_app, ["--json", "files", "list"])

    assert table.exit_code == 0
    assert "cursor_xyz" in table.output
    assert json.loads(as_json.output)["next_cursor"] == "cursor_xyz"


def test_patients_list_summary_page_forwards_the_next_cursor_too(
    runner: CliRunner, patched_build_client: FakeDiagnos
) -> None:
    """🇺🇸 The resume hint still shows with `--summary` on — the two features are independent.

    🇧🇷 A dica de retomar ainda aparece com `--summary` ligado — as duas funcionalidades são independentes.
    """
    patched_build_client.patients.list = lambda **kwargs: Page(  # type: ignore[method-assign]
        items=[PATIENT_ITEM], next_cursor="cursor_abc"
    )

    result = runner.invoke(typer_app, ["patients", "list", "--summary"])

    assert result.exit_code == 0
    assert "cursor_abc" in result.output
    assert "Jane" in result.output
