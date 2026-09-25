"""🇺🇸 Shared test fixtures: a fake `Diagnos` (`diagnos` is never touched over the network here) and a `TestClient`.

Every fake resource below only has to satisfy the same duck-typed shape
`vault.py`'s dependency (`diagnos_api.deps.get_vault`) hands routers — the
real `Diagnos`, `Patients`, `Exams`, `Drives` classes are never
subclassed or imported for their behavior, only their public method
signatures are mirrored (`apps/sdk/src/diagnos/resources/*.py`). That keeps
these tests exercising exactly one thing: this package's own HTTP/mTLS/error
wiring, never the SDK's.

🇧🇷 Fixtures compartilhadas de teste: um `Diagnos` falso (`diagnos` nunca é
tocado pela rede aqui) e um `TestClient`.

Todo recurso falso abaixo só precisa satisfazer a mesma forma duck-typed que
a dependência de `vault.py` (`diagnos_api.deps.get_vault`) entrega às rotas
— as classes de verdade `Diagnos`, `Patients`, `Exams`, `Drives` nunca são
subclassificadas nem importadas pelo comportamento, só as assinaturas de
método público são espelhadas (`apps/sdk/src/diagnos/resources/*.py`). Isso
mantém estes testes exercitando exatamente uma coisa: a fiação de
HTTP/mTLS/erro deste pacote, nunca a do SDK.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

import pytest
from diagnos import (
    DocumentIndex,
    DocumentListItem,
    DriveNode,
    Exam,
    ExamRecord,
    ExamSummary,
    NotFoundError,
    Page,
    Patient,
    PatientRecord,
    PatientSummary,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from diagnos_api.app import create_app
from diagnos_api.mtls import ClientIdentity
from diagnos_api.settings import ApiSettings

WORKSPACE_ID = "ws_test"

# 🇺🇸 The identity every mTLS-gated test uses unless it deliberately omits
# `trusted_test_identity` to exercise the "no certificate" path
# (`test_mtls.py`) — see `mtls.require_client_certificate`'s docstring for
# why this parameter only ever exists in tests.
# 🇧🇷 A identidade que todo teste travado por mTLS usa a menos que omita
# `trusted_test_identity` de propósito para exercitar o caminho "sem
# certificado" (`test_mtls.py`) — veja a docstring de
# `mtls.require_client_certificate` para o porquê deste parâmetro só existir
# em teste.
TRUSTED_IDENTITY = ClientIdentity(common_name="ci-client", serial="01")


def _index(document_id: str, *, resource: str, security_group_id: str, **extra: Any) -> DocumentIndex:
    """🇺🇸 A vault-shaped `DocumentIndex` with one committed version, for the fakes below to hand back.

    🇧🇷 Um `DocumentIndex` no formato do cofre com uma versão confirmada, para os fakes abaixo devolverem.
    """
    return DocumentIndex.model_validate(
        {
            "document_id": document_id,
            "workspace_id": WORKSPACE_ID,
            "resource": resource,
            "security_group_id": security_group_id,
            "encrypted_keys": {},
            "streams": {
                "data": {
                    "latest_version_id": "v1",
                    "versions": [
                        {"version_id": "v1", "size": 100, "created_at": "2024-01-01T00:00:00Z", "created_by": "t"}
                    ],
                    "pending_version_id": None,
                }
            },
            "created_at": "2024-01-01T00:00:00Z",
            "created_by": "tester",
            "updated_at": "2024-01-01T00:00:00Z",
            **extra,
        }
    )


class FakePatients:
    """🇺🇸 Enough of `Patients` (`apps/sdk/src/diagnos/resources/patients.py`) for the routes in `routers/patients.py`.

    Stateful on purpose — a create followed by a get must return what was
    created — and `calls` records every keyword the routes forwarded, so a
    test can assert the HTTP → SDK mapping without a real vault.

    🇧🇷 O suficiente de `Patients` (`apps/sdk/src/diagnos/resources/patients.py`) para as rotas de `routers/patients.py`.

    Com estado de propósito — criar e depois buscar precisa devolver o que
    foi criado — e `calls` registra todo argumento nomeado que as rotas
    repassaram, para um teste assertar o mapeamento HTTP → SDK sem cofre real.
    """

    def __init__(self) -> None:
        """🇺🇸 Starts empty. `raise_on_create` lets a test force a specific `diagnos` error out of `create`.

        🇧🇷 Começa vazio. `raise_on_create` deixa um teste forçar um erro específico do `diagnos` em `create`.
        """
        self._by_id: dict[str, Patient] = {}
        self._counter = 0
        self.raise_on_create: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs: Any) -> Page[DocumentListItem[PatientSummary]]:
        """🇺🇸 Every stored patient with its summary, unfiltered. 🇧🇷 Todo paciente guardado com o resumo, sem filtro."""
        self.calls.append(("list", kwargs))
        items = [DocumentListItem[PatientSummary](index=p.index, summary=p.summary) for p in self._by_id.values()]
        return Page(items=items, next_cursor=None)

    def create(self, record: PatientRecord, **kwargs: Any) -> Patient:
        """🇺🇸 Stores `record` under a freshly minted id, or raises `raise_on_create` if a test set one.

        🇧🇷 Guarda `record` sob um id recém-criado, ou lança `raise_on_create` se um teste tiver setado um.
        """
        self.calls.append(("create", kwargs))
        if self.raise_on_create is not None:
            raise self.raise_on_create
        self._counter += 1
        patient_id = f"patient_{self._counter}"
        index = _index(patient_id, resource="patients", security_group_id=kwargs["security_group"])
        patient = Patient(
            index=index, record=record, summary=PatientSummary.of(record, kwargs.get("tags", ())), version_id="v1"
        )
        self._by_id[patient_id] = patient
        return patient

    def get(self, patient_id: str, **kwargs: Any) -> Patient:
        """🇺🇸 The stored `Patient`, or `NotFoundError` — exactly what `Patients.get` raises for an unknown id.

        🇧🇷 O `Patient` guardado, ou `NotFoundError` — exatamente o que `Patients.get` lança para um id desconhecido.
        """
        self.calls.append(("get", kwargs))
        return self._find(patient_id)

    def _find(self, patient_id: str) -> Patient:
        """🇺🇸 Lookup without recording a call. 🇧🇷 Busca sem registrar chamada."""
        try:
            return self._by_id[patient_id]
        except KeyError:
            raise NotFoundError(code="DocumentNotFound", message=f"no patient {patient_id!r}", status=404) from None

    def update(self, patient_id: str, record: PatientRecord, **kwargs: Any) -> Patient:
        """🇺🇸 Replaces the stored record, keeping the same index.

        🇧🇷 Substitui o registro guardado, mantendo o índice.
        """
        self.calls.append(("update", kwargs))
        current = self._find(patient_id)
        updated = current.model_copy(update={"record": record})
        self._by_id[patient_id] = updated
        return updated

    def _flag(self, patient_id: str, **flags: bool) -> DocumentIndex:
        """🇺🇸 Applies a flag to the stored index. 🇧🇷 Aplica uma flag ao índice guardado."""
        current = self._find(patient_id)
        index = current.index.model_copy(update=flags)
        self._by_id[patient_id] = current.model_copy(update={"index": index})
        return index

    def archive(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Sets `is_archived`. 🇧🇷 Liga `is_archived`."""
        return self._flag(patient_id, is_archived=True)

    def unarchive(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Clears `is_archived`. 🇧🇷 Desliga `is_archived`."""
        return self._flag(patient_id, is_archived=False)

    def delete(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Sets `is_deleted`. 🇧🇷 Liga `is_deleted`."""
        return self._flag(patient_id, is_deleted=True)

    def restore(self, patient_id: str) -> DocumentIndex:
        """🇺🇸 Clears `is_deleted`. 🇧🇷 Desliga `is_deleted`."""
        return self._flag(patient_id, is_deleted=False)


class FakeExams:
    """🇺🇸 Enough of `Exams` (`apps/sdk/src/diagnos/resources/exams.py`) for the routes in `routers/exams.py`.

    🇧🇷 O suficiente de `Exams` (`apps/sdk/src/diagnos/resources/exams.py`) para as rotas de `routers/exams.py`.
    """

    def __init__(self) -> None:
        """🇺🇸 Starts empty. 🇧🇷 Começa vazio."""
        self._by_id: dict[str, Exam] = {}
        self._counter = 0
        self.raise_on_create: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs: Any) -> Page[DocumentListItem[ExamSummary]]:
        """🇺🇸 Every stored exam with its summary. 🇧🇷 Todo exame guardado com o resumo."""
        self.calls.append(("list", kwargs))
        items = [DocumentListItem[ExamSummary](index=e.index, summary=e.summary) for e in self._by_id.values()]
        return Page(items=items, next_cursor=None)

    def create(self, record: ExamRecord, *, patient_id: str, security_group: str) -> Exam:
        """🇺🇸 Stores `record`, linking only `patient_id` into the clear `meta`, mirroring `Exams.create`.

        🇧🇷 Guarda `record`, ligando só o `patient_id` ao `meta` em claro, espelhando `Exams.create`.
        """
        self.calls.append(("create", {"patient_id": patient_id, "security_group": security_group}))
        if self.raise_on_create is not None:
            raise self.raise_on_create
        self._counter += 1
        exam_id = f"exam_{self._counter}"
        index = _index(exam_id, resource="exams", security_group_id=security_group, meta={"patient_id": patient_id})
        exam = Exam(index=index, record=record, summary=ExamSummary.of(record), version_id="v1")
        self._by_id[exam_id] = exam
        return exam

    def get(self, exam_id: str, **kwargs: Any) -> Exam:
        """🇺🇸 The stored `Exam`, or `NotFoundError`. 🇧🇷 O `Exam` guardado, ou `NotFoundError`."""
        self.calls.append(("get", kwargs))
        return self._find(exam_id)

    def _find(self, exam_id: str) -> Exam:
        """🇺🇸 Lookup without recording a call. 🇧🇷 Busca sem registrar chamada."""
        try:
            return self._by_id[exam_id]
        except KeyError:
            raise NotFoundError(code="DocumentNotFound", message=f"no exam {exam_id!r}", status=404) from None

    def update(self, exam_id: str, record: ExamRecord, **kwargs: Any) -> Exam:
        """🇺🇸 Replaces the stored record. 🇧🇷 Substitui o registro guardado."""
        self.calls.append(("update", kwargs))
        current = self._find(exam_id)
        updated = current.model_copy(update={"record": record, "summary": ExamSummary.of(record)})
        self._by_id[exam_id] = updated
        return updated

    def _flag(self, exam_id: str, **flags: bool) -> DocumentIndex:
        """🇺🇸 Applies a flag to the stored index. 🇧🇷 Aplica uma flag ao índice guardado."""
        current = self._find(exam_id)
        index = current.index.model_copy(update=flags)
        self._by_id[exam_id] = current.model_copy(update={"index": index})
        return index

    def archive(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Sets `is_archived`. 🇧🇷 Liga `is_archived`."""
        return self._flag(exam_id, is_archived=True)

    def unarchive(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Clears `is_archived`. 🇧🇷 Desliga `is_archived`."""
        return self._flag(exam_id, is_archived=False)

    def delete(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Sets `is_deleted`. 🇧🇷 Liga `is_deleted`."""
        return self._flag(exam_id, is_deleted=True)

    def restore(self, exam_id: str) -> DocumentIndex:
        """🇺🇸 Clears `is_deleted`. 🇧🇷 Desliga `is_deleted`."""
        return self._flag(exam_id, is_deleted=False)


class FakeDrive:
    """🇺🇸 Enough of `Drive` (`apps/sdk/src/diagnos/resources/drives.py`) for the routes in `routers/files.py`.

    🇧🇷 O suficiente de `Drive` (`apps/sdk/src/diagnos/resources/drives.py`) para as rotas de `routers/files.py`.
    """

    def __init__(self, security_group_id: str) -> None:
        """🇺🇸 Starts empty. `last_upload` records what `upload` last received, for `test_files.py` to assert on.

        🇧🇷 Começa vazio. `last_upload` guarda o que `upload` recebeu por último, para `test_files.py` assertar.
        """
        self._security_group_id = security_group_id
        self._nodes: dict[str, DriveNode] = {}
        self._data: dict[str, bytes] = {}
        self._names: dict[str, str | None] = {}
        self._counter = 0
        self.last_upload: dict[str, Any] | None = None

    def list(
        self,
        *,
        exam_id: str | None = None,
        include_pending: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> Page[DriveNode]:
        """🇺🇸 Every stored node. 🇧🇷 Todo nó guardado."""
        return Page(items=list(self._nodes.values()), next_cursor=None)

    def get(self, node_id: str) -> DriveNode:
        """🇺🇸 The stored `DriveNode`, or `NotFoundError`. 🇧🇷 O `DriveNode` guardado, ou `NotFoundError`."""
        try:
            return self._nodes[node_id]
        except KeyError:
            raise NotFoundError(code="DriveNodeNotFound", message=f"no node {node_id!r}", status=404) from None

    def upload(
        self,
        source: str | os.PathLike[str] | bytes | BinaryIO,
        *,
        name: str | None = None,
        mime_type: str | None = None,
        exam_id: str | None = None,
    ) -> DriveNode:
        """🇺🇸 Reads `source` fully (mirroring `Drive.upload`'s accepted input shapes) and stores it as a node.

        🇧🇷 Lê `source` por inteiro (espelhando as formas de entrada aceitas por `Drive.upload`) e o guarda como um nó.
        """
        if isinstance(source, bytes):
            data = source
        elif isinstance(source, (str, os.PathLike)):
            data = Path(source).read_bytes()
        else:
            data = source.read()
        self._counter += 1
        node_id = f"node_{self._counter}"
        node = DriveNode(
            node_id=node_id,
            workspace_id=WORKSPACE_ID,
            security_group_id=self._security_group_id,
            exam_id=exam_id,
            status="ready",
            mode="single",
            declared_size=len(data),
            size=len(data),
            mime_type=mime_type,
            media_kind="other",
            storage_path=f"drive/{self._security_group_id}/{node_id}",
            created_by="tester",
            created_at="2024-01-01T00:00:00Z",
        )
        self._nodes[node_id] = node
        self._data[node_id] = data
        self._names[node_id] = name
        self.last_upload = {"data": data, "name": name, "mime_type": mime_type, "exam_id": exam_id}
        return node

    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """🇺🇸 Yields the stored bytes in two chunks, like the SDK's lazy decryptor.

        🇧🇷 Entrega os bytes em dois pedaços, como o decifrador preguiçoso do SDK.
        """
        data = self.download(node_id)
        assert data is not None
        half = len(data) // 2
        yield data[:half]
        yield data[half:]

    def download(self, node_id: str, destination: str | os.PathLike[str] | BinaryIO | None = None) -> bytes | None:
        """🇺🇸 Mirrors `Drive.download`'s three destination shapes.

        🇧🇷 Espelha as três formas de destino de `Drive.download`.
        """
        data = self._data[node_id]
        if destination is None:
            return data
        if isinstance(destination, (str, os.PathLike)):
            Path(destination).write_bytes(data)
            return None
        destination.write(data)
        return None

    def name_of(self, node: DriveNode) -> str | None:
        """🇺🇸 The plaintext name `upload` stored for this node. 🇧🇷 O nome em claro que `upload` guardou para este nó."""
        return self._names.get(node.node_id)


class FakeDrives:
    """🇺🇸 Enough of `Drives` (`apps/sdk/src/diagnos/resources/drives.py`) to hand out one `FakeDrive` per group.

    🇧🇷 O suficiente de `Drives` (`apps/sdk/src/diagnos/resources/drives.py`) para entregar um `FakeDrive` por grupo.
    """

    def __init__(self) -> None:
        """🇺🇸 Starts empty; a `FakeDrive` is created on first request per security group.

        🇧🇷 Começa vazio; um `FakeDrive` é criado na primeira solicitação por security group.
        """
        self._drives: dict[str, FakeDrive] = {}

    def drive(self, security_group_id: str) -> FakeDrive:
        """🇺🇸 The same `FakeDrive` instance for a given `security_group_id`, across calls.

        🇧🇷 A mesma instância de `FakeDrive` para um dado `security_group_id`, entre chamadas.
        """
        if security_group_id not in self._drives:
            self._drives[security_group_id] = FakeDrive(security_group_id)
        return self._drives[security_group_id]


@dataclass
class FakeDiagnos:
    """🇺🇸 Stands in for `Diagnos` (`client.py` in the SDK): fixed identity, in-memory resources, counted lifecycle.

    🇧🇷 Substitui `Diagnos` (`client.py` do SDK): identidade fixa, recursos em memória, ciclo de vida contado.
    """

    workspace_id: str = WORKSPACE_ID
    account_id: str = "acc_test"
    security_groups: list[str] = field(default_factory=lambda: ["sg1", "sg2"])
    patients: FakePatients = field(default_factory=FakePatients)
    exams: FakeExams = field(default_factory=FakeExams)
    drives: FakeDrives = field(default_factory=FakeDrives)
    unlock_calls: int = 0
    close_calls: int = 0
    lock_calls: int = 0

    def unlock(self) -> None:
        """🇺🇸 Counts the call; a fake session needs no real enrollment.

        🇧🇷 Conta a chamada; uma sessão falsa não precisa de enrollment de verdade.
        """
        self.unlock_calls += 1

    def close(self) -> None:
        """🇺🇸 Counts the call. 🇧🇷 Conta a chamada."""
        self.close_calls += 1

    def lock(self) -> None:
        """🇺🇸 Counts the call. 🇧🇷 Conta a chamada."""
        self.lock_calls += 1


@pytest.fixture
def fake_vault() -> FakeDiagnos:
    """🇺🇸 A fresh `FakeDiagnos`, empty, per test. 🇧🇷 Um `FakeDiagnos` novo, vazio, por teste."""
    return FakeDiagnos()


@pytest.fixture
def api_settings() -> ApiSettings:
    """🇺🇸 mTLS paths that never have to exist on disk: `create_app` never opens them itself.

    Only `ssl_config_for_uvicorn` (exercised in `test_mtls.py` as a plain
    dict, never fed to a real `ssl.SSLContext`) and the real `uvicorn.run`
    in `main.py` ever read these paths — building an app for tests never
    touches the filesystem for them.

    🇧🇷 Paths de mTLS que nunca precisam existir em disco: `create_app` nunca
    os abre sozinho.

    Só `ssl_config_for_uvicorn` (exercitado em `test_mtls.py` como um dict
    puro, nunca alimentado a um `ssl.SSLContext` de verdade) e o
    `uvicorn.run` de verdade em `main.py` leem estes paths — construir um
    app para teste nunca toca o sistema de arquivos por causa deles.
    """
    return ApiSettings(mtls_ca_file="/ca.pem", tls_cert_file="/tls.pem", tls_key_file="/tls-key.pem")


def build_app(
    fake_vault: FakeDiagnos,
    api_settings: ApiSettings,
    *,
    trusted_test_identity: ClientIdentity | None = TRUSTED_IDENTITY,
) -> FastAPI:
    """🇺🇸 `create_app` against `fake_vault`, defaulting to `TRUSTED_IDENTITY` — pass `None` for the "no cert" path.

    🇧🇷 `create_app` contra `fake_vault`, com `TRUSTED_IDENTITY` por padrão —
    passe `None` para o caminho "sem certificado".
    """
    return create_app(api_settings, fake_vault, trusted_test_identity=trusted_test_identity)


@pytest.fixture
def client(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> Iterator[TestClient]:
    """🇺🇸 A `TestClient` authenticated as `TRUSTED_IDENTITY` — the common case every route test starts from.

    🇧🇷 Um `TestClient` autenticado como `TRUSTED_IDENTITY` — o caso comum de onde todo teste de rota parte.
    """
    with TestClient(build_app(fake_vault, api_settings)) as test_client:
        yield test_client
