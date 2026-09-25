"""🇺🇸 Shared fixtures: a fake `Diagnos` (no network) and the `typer.testing.CliRunner`.

Every test monkeypatches `diagnos_cli.context.build_client` — never
`diagnos_cli.commands.<module>.build_client` — because every command module
calls it as `context.build_client(...)` (an attribute lookup on the module,
not a name bound at import time). Patching the name inside a command module
would silently miss whichever commands import `context` a different way; one
patch point covers every command.

🇧🇷 Fixtures compartilhadas: uma `Diagnos` falsa (sem rede) e o
`typer.testing.CliRunner`.

Todo teste faz monkeypatch de `diagnos_cli.context.build_client` — nunca de
`diagnos_cli.commands.<module>.build_client` — porque todo módulo de comando
chama isto como `context.build_client(...)` (uma busca de atributo no
módulo, não um nome vinculado na importação). Aplicar o patch no nome dentro
de um módulo de comando passaria batido, em silêncio, por qualquer comando
que importe `context` de outro jeito; um único ponto de patch cobre todo
comando.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from diagnos import (
    DocumentIndex,
    DriveNode,
    Exam,
    ExamRecord,
    NotFoundError,
    Page,
    Patient,
    PatientRecord,
)
from typer.testing import CliRunner

FIXED_NOW = "2026-09-08T12:00:00Z"

PATIENT_INDEX = DocumentIndex(
    document_id="pat_1",
    workspace_id="ws_1",
    resource="patients",
    security_groups=["sg_oncology"],
    encrypted_keys={},
    latest_version_id="v1",
    versions=[],
    created_at=FIXED_NOW,
    created_by="svc_1",
    updated_at=FIXED_NOW,
)
PATIENT_RECORD = PatientRecord(legal_name="Jane Doe", display_name="Jane")
PATIENT = Patient(index=PATIENT_INDEX, record=PATIENT_RECORD)

EXAM_INDEX = DocumentIndex(
    document_id="exam_1",
    workspace_id="ws_1",
    resource="exams",
    security_groups=["sg_oncology"],
    encrypted_keys={},
    latest_version_id="v1",
    versions=[],
    meta={"patient_id": "pat_1"},
    created_at=FIXED_NOW,
    created_by="svc_1",
    updated_at=FIXED_NOW,
)
EXAM_RECORD = ExamRecord(title="Chest CT")
EXAM = Exam(index=EXAM_INDEX, record=EXAM_RECORD)

DRIVE_NODE = DriveNode(
    node_id="node_1",
    workspace_id="ws_1",
    security_group_id="sg_oncology",
    exam_id="exam_1",
    status="ready",
    mode="single",
    declared_size=1234,
    size=1234,
    mime_type="application/dicom",
    media_kind="dicom",
    storage_path="ws_1/sg_oncology/node_1",
    created_by="svc_1",
    created_at=FIXED_NOW,
)

_DECRYPTED_NAMES = {"node_1": "chest_ct.dcm"}


class FakePatients:
    """🇺🇸 Fixed-data stand-in for `diagnos.resources.patients.Patients`. 🇧🇷 Substituto de dado fixo de `Patients`."""

    def list(self, **_: Any) -> Page[DocumentIndex]:
        return Page(items=[PATIENT_INDEX], next_cursor=None)

    def iter_all(self, **_: Any) -> Any:
        yield PATIENT_INDEX

    def get(self, patient_id: str, *, version_id: str | None = None) -> Patient:
        if patient_id != PATIENT.id:
            raise NotFoundError(code="PatientNotFound", message=f"no such patient {patient_id!r}", status=404)
        return PATIENT

    def create(self, record: Any, *, security_group: Any, specialist_ids: Any = None) -> Patient:
        return PATIENT

    def update(self, patient_id: str, record: Any, *, specialist_ids: Any = None) -> Patient:
        return PATIENT

    def archive(self, patient_id: str) -> DocumentIndex:
        return PATIENT_INDEX

    def unarchive(self, patient_id: str) -> DocumentIndex:
        return PATIENT_INDEX

    def delete(self, patient_id: str) -> DocumentIndex:
        return PATIENT_INDEX


class FakeExams:
    """🇺🇸 Fixed-data stand-in for `diagnos.resources.exams.Exams`. 🇧🇷 Substituto de dado fixo de `Exams`."""

    def list(self, **_: Any) -> Page[DocumentIndex]:
        return Page(items=[EXAM_INDEX], next_cursor=None)

    def iter_all(self, **_: Any) -> Any:
        yield EXAM_INDEX

    def get(self, exam_id: str, *, version_id: str | None = None) -> Exam:
        if exam_id != EXAM.id:
            raise NotFoundError(code="ExamNotFound", message=f"no such exam {exam_id!r}", status=404)
        return EXAM

    def create(self, record: Any, *, patient_id: str, security_group: Any, modality: str | None = None) -> Exam:
        return EXAM

    def update(self, exam_id: str, record: Any, *, modality: str | None = None) -> Exam:
        return EXAM

    def archive(self, exam_id: str) -> DocumentIndex:
        return EXAM_INDEX

    def unarchive(self, exam_id: str) -> DocumentIndex:
        return EXAM_INDEX

    def delete(self, exam_id: str) -> DocumentIndex:
        return EXAM_INDEX


class FakeDrive:
    """🇺🇸 Fixed-data stand-in for one `diagnos.resources.drives.Drive`. 🇧🇷 Substituto de dado fixo de uma `Drive`."""

    def list(self, **_: Any) -> Page[DriveNode]:
        return Page(items=[DRIVE_NODE], next_cursor=None)

    def iter_all(self, **_: Any) -> Any:
        yield DRIVE_NODE

    def get(self, node_id: str) -> DriveNode:
        if node_id != DRIVE_NODE.node_id:
            raise NotFoundError(code="NodeNotFound", message=f"no such node {node_id!r}", status=404)
        return DRIVE_NODE

    def upload_many(self, sources: Any, *, exam_id: str | None = None) -> list[DriveNode]:
        return [DRIVE_NODE for _ in sources]

    def download(self, node_id: str, destination: str | Path | Any | None = None) -> bytes | None:
        data = b"fake-encrypted-then-decrypted-bytes"
        if destination is None:
            return data
        if isinstance(destination, (str, Path)):
            Path(destination).write_bytes(data)
            return None
        destination.write(data)
        return None

    def name_of(self, node: DriveNode) -> str | None:
        return _DECRYPTED_NAMES.get(node.node_id)


class FakeDrives:
    """🇺🇸 Fixed-data stand-in for `diagnos.resources.drives.Drives`. 🇧🇷 Substituto de dado fixo de `Drives`."""

    def drive(self, security_group_id: str) -> FakeDrive:
        return FakeDrive()


class FakeDiagnos:
    """🇺🇸 A whole fake `Diagnos`: no HTTP client, no crypto, fixed answers — exactly what the CLI tests should exercise.

    🇧🇷 Uma `Diagnos` inteira falsa: sem client HTTP, sem cripto, respostas
    fixas — exatamente o que `apps/cli/tests` deve exercitar.
    """

    def __init__(self) -> None:
        self.patients = FakePatients()
        self.exams = FakeExams()
        self.drives = FakeDrives()
        self._unlocked = False
        # 🇺🇸 A test overrides this (e.g. to `[]`) *before* invoking a command
        # to exercise the "nothing granted" branch of `groups`/`status
        # --check` — the property below only ever returns it post-`unlock()`,
        # exactly like the real `Diagnos.security_groups`.
        # 🇧🇷 Um teste sobrescreve isto (ex.: para `[]`) *antes* de invocar um
        # comando para exercitar o ramo "nada concedido" de `groups`/`status
        # --check` — a property abaixo só o devolve depois de `unlock()`,
        # exatamente como a `Diagnos.security_groups` de verdade.
        self.granted_groups: list[str] = ["sg_oncology"]

    @property
    def workspace_id(self) -> str:
        return "ws_1"

    @property
    def account_id(self) -> str:
        return "acct_1"

    @property
    def security_groups(self) -> list[str]:
        return self.granted_groups if self._unlocked else []

    def unlock(self) -> Any:
        self._unlocked = True
        return object()

    def lock(self) -> None:
        self._unlocked = False


@pytest.fixture
def fake_vault() -> FakeDiagnos:
    """🇺🇸 A fresh fake client per test — state (like `_unlocked`) never leaks between tests.

    🇧🇷 Uma client falsa nova por teste — estado (como `_unlocked`) nunca vaza entre testes.
    """
    return FakeDiagnos()


@pytest.fixture
def patched_build_client(monkeypatch: pytest.MonkeyPatch, fake_vault: FakeDiagnos) -> FakeDiagnos:
    """🇺🇸 Patches `diagnos_cli.context.build_client` to always hand back `fake_vault`, ignoring every argument.

    🇧🇷 Aplica patch em `diagnos_cli.context.build_client` para sempre devolver `fake_vault`, ignorando todo argumento.
    """
    import diagnos_cli.context as context_module

    monkeypatch.setattr(context_module, "build_client", lambda *args, **kwargs: fake_vault)
    return fake_vault


@pytest.fixture
def runner() -> CliRunner:
    """🇺🇸 `typer`'s test runner, invoking the real Typer app in-process.

    🇧🇷 O runner de teste do `typer`, invocando a app Typer real, no mesmo processo.
    """
    return CliRunner()
