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
    DocumentListItem,
    DriveNode,
    Exam,
    ExamRecord,
    ExamSummary,
    GroupKeyUnavailable,
    NotFoundError,
    Page,
    Patient,
    PatientRecord,
    PatientSummary,
)
from typer.testing import CliRunner

FIXED_NOW = "2026-09-08T12:00:00.000Z"


def _index(document_id: str, resource: str, **extra: Any) -> DocumentIndex:
    """🇺🇸 A vault-shaped index with one committed version on `data`.

    🇧🇷 Um índice no formato do cofre com uma versão em `data`.
    """
    return DocumentIndex.model_validate(
        {
            "document_id": document_id,
            "workspace_id": "ws_1",
            "resource": resource,
            "security_group_id": "sg_oncology",
            "encrypted_keys": {},
            "streams": {
                "data": {
                    "latest_version_id": "v1",
                    "versions": [{"version_id": "v1", "size": 120, "created_at": FIXED_NOW, "created_by": "svc_1"}],
                    "pending_version_id": None,
                }
            },
            "created_at": FIXED_NOW,
            "created_by": "svc_1",
            "updated_at": FIXED_NOW,
            **extra,
        }
    )


PATIENT_INDEX = _index("pat_1", "patients")
PATIENT_RECORD = PatientRecord(legal_name="Jane Doe", display_name="Jane")
PATIENT_SUMMARY = PatientSummary.of(PATIENT_RECORD, ["oncology"])
PATIENT = Patient(index=PATIENT_INDEX, record=PATIENT_RECORD, summary=PATIENT_SUMMARY, version_id="v1")
PATIENT_ITEM = DocumentListItem[PatientSummary](index=PATIENT_INDEX, summary=PATIENT_SUMMARY)

EXAM_INDEX = _index("exam_1", "exams", meta={"patient_id": "pat_1"})
EXAM_RECORD = ExamRecord(title="Chest CT", modality="CT", report_html="<p>No acute findings.</p>")
EXAM_SUMMARY = ExamSummary.of(EXAM_RECORD)
EXAM = Exam(index=EXAM_INDEX, record=EXAM_RECORD, summary=EXAM_SUMMARY, version_id="v1")
EXAM_ITEM = DocumentListItem[ExamSummary](index=EXAM_INDEX, summary=EXAM_SUMMARY)

DRIVE_NODE = DriveNode.model_validate(
    {
        "node_id": "node_1",
        "workspace_id": "ws_1",
        "security_group_id": "sg_oncology",
        "kind": "file",
        "exam_id": "exam_1",
        "status": "ready",
        "mode": "single",
        "declared_size": 1234,
        "size": 1234,
        "mime_type": "application/dicom",
        "media_kind": "dicom",
        "encrypted_name": {"salt": "s", "nonce": "n", "ciphertext": "c"},
        "encrypted_keys": {},
        "storage_path": "workspaces/ws_1/nodes/node_1",
        "created_by": "svc_1",
        "created_at": FIXED_NOW,
    }
)

_DECRYPTED_NAMES = {"node_1": "chest_ct.dcm"}


class FakePatients:
    """🇺🇸 Fixed-data stand-in for `diagnos.resources.patients.Patients`; `calls` records every keyword.

    🇧🇷 Substituto de dado fixo de `Patients`; `calls` registra todo argumento nomeado.
    """

    def __init__(self) -> None:
        """🇺🇸 No calls yet. 🇧🇷 Nenhuma chamada ainda."""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs: Any) -> Page[DocumentListItem[PatientSummary]]:
        self.calls.append(("list", kwargs))
        return Page(items=[PATIENT_ITEM], next_cursor=None)

    def iter_all(self, **kwargs: Any) -> Any:
        self.calls.append(("iter_all", kwargs))
        yield PATIENT_ITEM

    def get(self, patient_id: str, **kwargs: Any) -> Patient:
        self.calls.append(("get", kwargs))
        if patient_id != PATIENT.id:
            raise NotFoundError(code="DocumentNotFound", message=f"no such patient {patient_id!r}", status=404)
        return PATIENT

    def create(self, record: Any, **kwargs: Any) -> Patient:
        self.calls.append(("create", {"record": record, **kwargs}))
        return PATIENT

    def update(self, patient_id: str, record: Any, **kwargs: Any) -> Patient:
        self.calls.append(("update", {"record": record, **kwargs}))
        return PATIENT

    def archive(self, patient_id: str) -> DocumentIndex:
        return PATIENT_INDEX

    def unarchive(self, patient_id: str) -> DocumentIndex:
        return PATIENT_INDEX

    def delete(self, patient_id: str) -> DocumentIndex:
        return PATIENT_INDEX

    def restore(self, patient_id: str) -> DocumentIndex:
        return PATIENT_INDEX


class FakeExams:
    """🇺🇸 Fixed-data stand-in for `diagnos.resources.exams.Exams`; `calls` records every keyword.

    🇧🇷 Substituto de dado fixo de `Exams`; `calls` registra todo argumento nomeado.
    """

    def __init__(self) -> None:
        """🇺🇸 No calls yet. 🇧🇷 Nenhuma chamada ainda."""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs: Any) -> Page[DocumentListItem[ExamSummary]]:
        self.calls.append(("list", kwargs))
        return Page(items=[EXAM_ITEM], next_cursor=None)

    def iter_all(self, **kwargs: Any) -> Any:
        self.calls.append(("iter_all", kwargs))
        yield EXAM_ITEM

    def get(self, exam_id: str, **kwargs: Any) -> Exam:
        self.calls.append(("get", kwargs))
        if exam_id != EXAM.id:
            raise NotFoundError(code="DocumentNotFound", message=f"no such exam {exam_id!r}", status=404)
        return EXAM

    def create(self, record: Any, **kwargs: Any) -> Exam:
        self.calls.append(("create", {"record": record, **kwargs}))
        return EXAM

    def update(self, exam_id: str, record: Any, **kwargs: Any) -> Exam:
        self.calls.append(("update", {"record": record, **kwargs}))
        return EXAM

    def archive(self, exam_id: str) -> DocumentIndex:
        return EXAM_INDEX

    def unarchive(self, exam_id: str) -> DocumentIndex:
        return EXAM_INDEX

    def delete(self, exam_id: str) -> DocumentIndex:
        return EXAM_INDEX

    def restore(self, exam_id: str) -> DocumentIndex:
        return EXAM_INDEX


class FakeDrive:
    """🇺🇸 Fixed-data stand-in for `diagnos.Drive` / `diagnos.Drives`; `calls` records every keyword.

    🇧🇷 Substituto de dado fixo de `diagnos.Drive` / `diagnos.Drives`; `calls` registra todo argumento nomeado.
    """

    def __init__(self, security_group_id: str | None = None) -> None:
        """🇺🇸 No calls yet. 🇧🇷 Nenhuma chamada ainda."""
        self.security_group_id = security_group_id
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.names = dict(_DECRYPTED_NAMES)
        # 🇺🇸 Set to `True` to act like a session holding no key for the node's group.
        # 🇧🇷 Ligue para agir como uma sessão sem chave para o grupo do nó.
        self.locked = False

    def list(self, **kwargs: Any) -> Page[DriveNode]:
        self.calls.append(("list", kwargs))
        return Page(items=[DRIVE_NODE], next_cursor=None)

    def iter_all(self, **kwargs: Any) -> Any:
        self.calls.append(("iter_all", kwargs))
        yield DRIVE_NODE

    def get(self, node_id: str) -> DriveNode:
        if node_id != DRIVE_NODE.node_id:
            raise NotFoundError(code="DriveNodeNotFound", message=f"no such node {node_id!r}", status=404)
        return DRIVE_NODE

    def upload_many(self, sources: Any, **kwargs: Any) -> list[DriveNode]:
        self.calls.append(("upload_many", {"sources": list(sources), **kwargs}))
        return [DRIVE_NODE for _ in self.calls[-1][1]["sources"]]

    def create_folder(self, name: str, **kwargs: Any) -> str:
        self.calls.append(("create_folder", {"name": name, **kwargs}))
        return "folder_1"

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
        if self.locked:
            raise GroupKeyUnavailable(f"no key for {node.security_group_id!r}")
        return self.names.get(node.node_id)


class FakeDrives(FakeDrive):
    """🇺🇸 `vault.drives`: workspace-level reads plus `drive(group)`.

    🇧🇷 `vault.drives`: leituras do workspace mais `drive(grupo)`.
    """

    def __init__(self) -> None:
        """🇺🇸 Remembers the drives it handed out. 🇧🇷 Lembra os drives que entregou."""
        super().__init__()
        self.handed_out: dict[str, FakeDrive] = {}

    def drive(self, security_group_id: str) -> FakeDrive:
        return self.handed_out.setdefault(security_group_id, FakeDrive(security_group_id))


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
