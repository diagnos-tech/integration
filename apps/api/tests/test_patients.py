"""🇺🇸 `/v1/patients`: happy-path CRUD plus the `diagnos` → HTTP error mapping (`errors.py`).

🇧🇷 `/v1/patients`: CRUD do caminho feliz mais o mapeamento de erro `diagnos` → HTTP (`errors.py`).
"""

from __future__ import annotations

from diagnos import ConflictError, QuotaError
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


def test_list_is_anonymous_unless_summary_is_asked(client: TestClient) -> None:
    """🇺🇸 Rows carry `summary: null` by default; `?summary=true` adds the decrypted names and tags.

    🇧🇷 Linhas trazem `summary: null` por padrão; `?summary=true` acrescenta nomes e tags decifrados.
    """
    client.post("/v1/patients", json={**_create_body(), "tags": ["vip"]})

    anonymous = client.get("/v1/patients").json()["items"]
    named = client.get("/v1/patients", params={"summary": "true"}).json()["items"]

    assert anonymous[0]["summary"] is None
    assert anonymous[0]["index"]["security_group_id"] == "sg1"
    assert named[0]["summary"]["display_name"] == "Jane"
    assert named[0]["summary"]["tags"] == ["vip"]


def test_list_rejects_a_page_size_the_vault_would_refuse(client: TestClient) -> None:
    """🇺🇸 `limit` is bounded to 1..200 at the edge (§13). 🇧🇷 `limit` é limitado a 1..200 na borda (§13)."""
    assert client.get("/v1/patients", params={"limit": 201}).status_code == 422


def test_update_replaces_the_record_and_forwards_the_guards(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `PUT` sends a complete record; `tags: null` keeps tags; the version guard reaches the SDK.

    🇧🇷 `PUT` manda o registro completo; `tags: null` mantém as tags; a trava de versão chega ao SDK.
    """
    created = client.post("/v1/patients", json=_create_body())
    patient_id = created.json()["index"]["document_id"]

    updated = client.put(
        f"/v1/patients/{patient_id}",
        json={
            "record": {"legal_name": "Jane Doe, revised", "display_name": "Jane"},
            "expected_latest_version_id": "v1",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["record"]["legal_name"] == "Jane Doe, revised"
    assert fake_vault.patients.calls[-1] == (
        "update",
        {"tags": None, "specialist_ids": None, "expected_latest_version_id": "v1"},
    )


def test_get_forwards_version_and_draft_choice(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `version_id`/`include_draft` reach `Patients.get`. 🇧🇷 `version_id`/`include_draft` chegam a `Patients.get`."""
    patient_id = client.post("/v1/patients", json=_create_body()).json()["index"]["document_id"]

    response = client.get(f"/v1/patients/{patient_id}", params={"include_draft": "false", "version_id": "v1"})

    assert response.status_code == 200
    assert response.json()["version_id"] == "v1"
    assert fake_vault.patients.calls[-1] == ("get", {"version_id": "v1", "include_draft": False})


def test_a_typo_in_the_record_is_422_naming_the_field(client: TestClient) -> None:
    """🇺🇸 `birthdate` is refused with the real field name, before anything is encrypted.

    🇧🇷 `birthdate` é recusado com o nome do campo real, antes de qualquer coisa ser cifrada.
    """
    body = {
        "record": {"legal_name": "Jane Doe", "display_name": "Jane", "birthdate": "1990-01-01"},
        "security_group": "sg1",
    }

    response = client.post("/v1/patients", json=body)

    assert response.status_code == 422
    assert "birth_date" in response.text


def test_a_list_of_groups_is_422(client: TestClient) -> None:
    """🇺🇸 One document, one group. 🇧🇷 Um documento, um grupo."""
    response = client.post("/v1/patients", json={**_create_body(), "security_group": ["sg1", "sg2"]})
    assert response.status_code == 422


def test_lifecycle_flags_round_trip(client: TestClient) -> None:
    """🇺🇸 archive/unarchive/delete/restore flip the flags and return the index.

    🇧🇷 archive/unarchive/delete/restore trocam as flags e devolvem o índice.
    """
    patient_id = client.post("/v1/patients", json=_create_body()).json()["index"]["document_id"]

    assert client.post(f"/v1/patients/{patient_id}/archive").json()["is_archived"] is True
    assert client.post(f"/v1/patients/{patient_id}/unarchive").json()["is_archived"] is False
    assert client.delete(f"/v1/patients/{patient_id}").json()["is_deleted"] is True
    restored = client.post(f"/v1/patients/{patient_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["is_deleted"] is False


def test_a_version_conflict_is_409(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `DocumentVersionMismatch` from the SDK becomes 409 with its code. 🇧🇷 `DocumentVersionMismatch` vira 409."""
    fake_vault.patients.raise_on_create = ConflictError(
        code="DocumentVersionMismatch", message="another version was committed", status=409
    )

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DocumentVersionMismatch"


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
