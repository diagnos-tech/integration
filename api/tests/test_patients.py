"""🇺🇸 `/v1/patients`: happy-path CRUD plus the `diagnos` → HTTP error mapping (`errors.py`).

🇧🇷 `/v1/patients`: CRUD do caminho feliz mais o mapeamento de erro `diagnos` → HTTP (`errors.py`).
"""

from __future__ import annotations

from diagnos import QuotaError
from fastapi.testclient import TestClient

from conftest import FakeDiagnos


def _create_body() -> dict[str, object]:
    """🇺🇸 A minimal valid `POST /v1/patients` body. 🇧🇷 Um corpo mínimo válido de `POST /v1/patients`."""
    return {
        "record": {"legal_name": "Jane Doe", "display_name": "Jane"},
        "security_group": "sg1",
    }


def test_create_then_get_round_trips_the_record(client: TestClient) -> None:
    """🇺🇸 A created patient's `record` comes back unchanged from `GET /v1/patients/{id}`.

    🇧🇷 O `record` de um paciente criado volta sem mudar de `GET /v1/patients/{id}`.
    """
    created = client.post("/v1/patients", json=_create_body())
    assert created.status_code == 201
    patient_id = created.json()["index"]["document_id"]

    fetched = client.get(f"/v1/patients/{patient_id}")

    assert fetched.status_code == 200
    assert fetched.json()["record"]["legal_name"] == "Jane Doe"


def test_list_includes_created_patients(client: TestClient) -> None:
    """🇺🇸 A patient created via `POST` shows up in `GET /v1/patients`'s index list.

    🇧🇷 Um paciente criado via `POST` aparece na lista de índices de `GET /v1/patients`.
    """
    client.post("/v1/patients", json=_create_body())

    listed = client.get("/v1/patients")

    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


def test_update_replaces_the_record(client: TestClient) -> None:
    """🇺🇸 `PUT` reuses the patient's existing DEK — the caller only ever sees a fresh `record` come back.

    🇧🇷 `PUT` reusa a DEK existente do paciente — quem chama só vê um `record` novo voltar.
    """
    created = client.post("/v1/patients", json=_create_body())
    patient_id = created.json()["index"]["document_id"]

    updated = client.put(
        f"/v1/patients/{patient_id}", json={"record": {"legal_name": "Jane Doe, revised", "display_name": "Jane"}}
    )

    assert updated.status_code == 200
    assert updated.json()["record"]["legal_name"] == "Jane Doe, revised"


def test_archive_then_unarchive_round_trip(client: TestClient) -> None:
    """🇺🇸 Both mutation routes delegate straight to the fake and return its index unchanged.

    🇧🇷 As duas rotas de mutação delegam direto ao fake e devolvem o índice dele sem mudar.
    """
    created = client.post("/v1/patients", json=_create_body())
    patient_id = created.json()["index"]["document_id"]

    archived = client.post(f"/v1/patients/{patient_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["document_id"] == patient_id

    unarchived = client.post(f"/v1/patients/{patient_id}/unarchive")
    assert unarchived.status_code == 200
    assert unarchived.json()["document_id"] == patient_id


def test_delete_removes_the_patient(client: TestClient) -> None:
    """🇺🇸 After `DELETE`, the same id 404s on `GET`. 🇧🇷 Depois do `DELETE`, o mesmo id dá 404 no `GET`."""
    created = client.post("/v1/patients", json=_create_body())
    patient_id = created.json()["index"]["document_id"]

    deleted = client.delete(f"/v1/patients/{patient_id}")
    assert deleted.status_code == 200

    missing = client.get(f"/v1/patients/{patient_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PatientNotFound"


def test_get_unknown_patient_is_404_with_the_uniform_envelope(client: TestClient) -> None:
    """🇺🇸 `NotFoundError` from the SDK becomes a 404 in `{"error": {code, message, trace_id}}` shape.

    🇧🇷 `NotFoundError` do SDK vira um 404 na forma `{"error": {code, message, trace_id}}`.
    """
    response = client.get("/v1/patients/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body["error"]) == {"code", "message", "trace_id"}


def test_quota_exceeded_on_create_is_402(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `QuotaError` from `Patients.create` becomes 402 — `docs/PROTOCOL.md §12`'s "no credit" case.

    🇧🇷 `QuotaError` de `Patients.create` vira 402 — o caso "sem crédito" de `docs/PROTOCOL.md §12`.
    """
    fake_vault.patients.raise_on_create = QuotaError(code="QuotaExceeded", message="no credit left", status=402)

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 402
    assert response.json()["error"]["code"] == "QuotaExceeded"
