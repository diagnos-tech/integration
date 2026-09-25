"""🇺🇸 `/v1/exams`: happy-path CRUD plus archive/unarchive — the exam-side twin of `test_patients.py`.

`routers/exams.py` mirrors `routers/patients.py` line for line (same
"thin HTTP face" reasoning, same fake shape in `conftest.py`); this file
exists because `test_patients.py` alone leaves every line in `exams.py`
untouched — a fake being *reachable* through `conftest.py` is not the same
as a router actually being called.

🇧🇷 `/v1/exams`: CRUD do caminho feliz mais archive/unarchive — o gêmeo do
lado exame de `test_patients.py`.

`routers/exams.py` espelha `routers/patients.py` linha a linha (mesmo
raciocínio de "face HTTP fina", mesma forma de fake em `conftest.py`); este
arquivo existe porque só `test_patients.py` deixa toda linha de `exams.py`
intocada — um fake estar *alcançável* via `conftest.py` não é o mesmo que um
roteador ser de fato chamado.
"""

from __future__ import annotations

from diagnos import QuotaError
from fastapi.testclient import TestClient

from conftest import FakeDiagnos


def _create_body() -> dict[str, object]:
    """🇺🇸 A minimal valid `POST /v1/exams` body. 🇧🇷 Um corpo mínimo válido de `POST /v1/exams`."""
    return {
        "record": {"title": "Chest CT"},
        "patient_id": "patient_1",
        "security_group": "sg1",
        "modality": "CT",
    }


def test_create_then_get_round_trips_the_record(client: TestClient) -> None:
    """🇺🇸 A created exam's `record` comes back unchanged from `GET /v1/exams/{id}`.

    🇧🇷 O `record` de um exame criado volta sem mudar de `GET /v1/exams/{id}`.
    """
    created = client.post("/v1/exams", json=_create_body())
    assert created.status_code == 201
    exam_id = created.json()["index"]["document_id"]
    assert created.json()["index"]["meta"]["patient_id"] == "patient_1"

    fetched = client.get(f"/v1/exams/{exam_id}")

    assert fetched.status_code == 200
    assert fetched.json()["record"]["title"] == "Chest CT"


def test_list_includes_created_exams(client: TestClient) -> None:
    """🇺🇸 An exam created via `POST` shows up in `GET /v1/exams`'s index list.

    🇧🇷 Um exame criado via `POST` aparece na lista de índices de `GET /v1/exams`.
    """
    client.post("/v1/exams", json=_create_body())

    listed = client.get("/v1/exams")

    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


def test_update_replaces_the_record(client: TestClient) -> None:
    """🇺🇸 `PUT` reuses the exam's existing DEK — the caller only ever sees a fresh `record` come back.

    🇧🇷 `PUT` reusa a DEK existente do exame — quem chama só vê um `record` novo voltar.
    """
    created = client.post("/v1/exams", json=_create_body())
    exam_id = created.json()["index"]["document_id"]

    updated = client.put(f"/v1/exams/{exam_id}", json={"record": {"title": "Chest CT, revised"}})

    assert updated.status_code == 200
    assert updated.json()["record"]["title"] == "Chest CT, revised"


def test_archive_then_unarchive_round_trip(client: TestClient) -> None:
    """🇺🇸 Both mutation routes delegate straight to the fake and return its index unchanged.

    🇧🇷 As duas rotas de mutação delegam direto ao fake e devolvem o índice dele sem mudar.
    """
    created = client.post("/v1/exams", json=_create_body())
    exam_id = created.json()["index"]["document_id"]

    archived = client.post(f"/v1/exams/{exam_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["document_id"] == exam_id

    unarchived = client.post(f"/v1/exams/{exam_id}/unarchive")
    assert unarchived.status_code == 200
    assert unarchived.json()["document_id"] == exam_id


def test_delete_removes_the_exam(client: TestClient) -> None:
    """🇺🇸 After `DELETE`, the same id 404s on `GET`. 🇧🇷 Depois do `DELETE`, o mesmo id dá 404 no `GET`."""
    created = client.post("/v1/exams", json=_create_body())
    exam_id = created.json()["index"]["document_id"]

    deleted = client.delete(f"/v1/exams/{exam_id}")
    assert deleted.status_code == 200

    missing = client.get(f"/v1/exams/{exam_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ExamNotFound"


def test_get_unknown_exam_is_404_with_the_uniform_envelope(client: TestClient) -> None:
    """🇺🇸 `NotFoundError` from the SDK becomes a 404 in `{"error": {code, message, trace_id}}` shape.

    🇧🇷 `NotFoundError` do SDK vira um 404 na forma `{"error": {code, message, trace_id}}`.
    """
    response = client.get("/v1/exams/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body["error"]) == {"code", "message", "trace_id"}


def test_quota_exceeded_on_create_is_402(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `QuotaError` from `Exams.create` becomes 402, same as the patient-side mapping.

    🇧🇷 `QuotaError` de `Exams.create` vira 402, igual ao mapeamento do lado paciente.
    """
    fake_vault.exams.raise_on_create = QuotaError(code="QuotaExceeded", message="no credit left", status=402)

    response = client.post("/v1/exams", json=_create_body())

    assert response.status_code == 402
    assert response.json()["error"]["code"] == "QuotaExceeded"
