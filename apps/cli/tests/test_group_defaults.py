"""🇺🇸 Where commands that write find their security group: `--group`, `DIAGNOS_GROUP`, the patient's, the only one.

A session approved for one group should never have to type it; a session
with several must choose, and is told the choices — sealing under the wrong
group hands a record to the wrong team.

🇧🇷 Onde os comandos que gravam acham o security group: `--group`, `DIAGNOS_GROUP`, o do paciente, o único.

Uma sessão aprovada para um grupo nunca deveria precisar digitá-lo; uma com
vários precisa escolher, e ouve quais são as opções — selar sob o grupo
errado entrega um registro à equipe errada.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .conftest import PATIENT_INDEX, FakeDiagnos

_CREATE_PATIENT = ["patients", "create", "--legal-name", "Jane Doe", "--display-name", "Jane"]


def _created_group(calls: list[tuple[str, dict[str, object]]]) -> object:
    """🇺🇸 The `security_group` the last `create` received. 🇧🇷 O `security_group` que o último `create` recebeu."""
    return next(kwargs for name, kwargs in reversed(calls) if name == "create")["security_group"]


def test_a_session_with_one_group_needs_no_flag(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 The only granted group is used, and stderr says which and why.

    🇧🇷 O único grupo concedido é usado, e o stderr diz qual e por quê.
    """
    result = runner.invoke(typer_app, _CREATE_PATIENT)

    assert result.exit_code == 0, result.output
    assert _created_group(patched_build_client.patients.calls) == "sg_oncology"
    assert "sg_oncology" in result.stderr
    assert "only group" in result.stderr


def test_the_environment_variable_needs_no_inference(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 `DIAGNOS_GROUP` is taken as given — nothing is inferred, nothing announced.

    🇧🇷 `DIAGNOS_GROUP` é usado como veio — nada é inferido, nada é anunciado.
    """
    patched_build_client.granted_groups = ["sg_oncology", "sg_cardio"]

    result = runner.invoke(typer_app, _CREATE_PATIENT, env={"DIAGNOS_GROUP": "sg_cardio"})

    assert result.exit_code == 0, result.output
    assert _created_group(patched_build_client.patients.calls) == "sg_cardio"
    assert "grupo" not in result.stderr


def test_the_flag_wins_over_the_environment(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 An explicit `--group` beats `DIAGNOS_GROUP`. 🇧🇷 Um `--group` explícito vence o `DIAGNOS_GROUP`."""
    result = runner.invoke(typer_app, [*_CREATE_PATIENT, "--group", "sg_x"], env={"DIAGNOS_GROUP": "sg_env"})

    assert result.exit_code == 0, result.output
    assert _created_group(patched_build_client.patients.calls) == "sg_x"


def test_several_groups_is_a_usage_error_that_lists_them(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 Ambiguity stops before anything is sealed, naming every choice and both ways to pick.

    🇧🇷 A ambiguidade para antes de qualquer selagem, nomeando toda opção e as duas formas de escolher.
    """
    patched_build_client.granted_groups = ["sg_oncology", "sg_cardio"]

    result = runner.invoke(typer_app, _CREATE_PATIENT)

    assert result.exit_code == 2
    assert "sg_oncology, sg_cardio" in result.output
    assert "DIAGNOS_GROUP" in result.output
    assert not any(name == "create" for name, _ in patched_build_client.patients.calls)


def test_no_group_at_all_says_who_can_fix_it(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 A session without any group key is told to ask an admin — not just "missing option".

    🇧🇷 Uma sessão sem chave de grupo nenhuma ouve que precisa pedir a um admin — não só "opção faltando".
    """
    patched_build_client.granted_groups = []

    result = runner.invoke(typer_app, _CREATE_PATIENT)

    assert result.exit_code == 2
    assert "admin" in result.output


def test_an_exam_goes_to_its_patients_group(
    runner: CliRunner, patched_build_client: FakeDiagnos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """🇺🇸 Without `--group`, the exam is sealed in the patient's group — even when that is not the session's only one.

    🇧🇷 Sem `--group`, o exame é selado no grupo do paciente — mesmo quando não é o único da sessão.
    """
    index = PATIENT_INDEX.model_copy(update={"security_group_id": "sg_cardio"})
    monkeypatch.setattr(patched_build_client.patients, "index", lambda patient_id: index, raising=False)

    result = runner.invoke(typer_app, ["exams", "create", "--patient", "pat_1", "--title", "CT"])

    assert result.exit_code == 0, result.output
    assert _created_group(patched_build_client.exams.calls) == "sg_cardio"
    assert "patient" in result.stderr


def test_files_upload_and_mkdir_use_the_only_group(
    runner: CliRunner, patched_build_client: FakeDiagnos, tmp_path: Path
) -> None:
    """🇺🇸 `files upload` and `files mkdir` resolve the group like `create`; `--quiet` keeps stderr silent.

    🇧🇷 `files upload` e `files mkdir` resolvem o grupo como o `create`; `--quiet` mantém o stderr calado.
    """
    scan = tmp_path / "scan.dcm"
    scan.write_bytes(b"dicom")

    uploaded = runner.invoke(typer_app, ["--quiet", "files", "upload", str(scan)])
    made = runner.invoke(typer_app, ["--quiet", "files", "mkdir", "Series 1"])

    assert uploaded.exit_code == 0, uploaded.output
    assert made.exit_code == 0, made.output
    assert list(patched_build_client.drives.handed_out) == ["sg_oncology"]
    assert "grupo" not in uploaded.stderr
    assert "grupo" not in made.stderr


@pytest.mark.parametrize("command", [["patients", "create"], ["files", "upload"], ["files", "mkdir"]])
def test_help_shows_the_environment_variable(runner: CliRunner, command: list[str]) -> None:
    """🇺🇸 `--help` names `DIAGNOS_GROUP`, so the default is discoverable without the README.

    🇧🇷 O `--help` nomeia `DIAGNOS_GROUP`, então o padrão é descobrível sem o README.
    """
    result = runner.invoke(typer_app, [*command, "--help"], terminal_width=200)

    assert result.exit_code == 0
    assert "DIAGNOS_GROUP" in result.output
