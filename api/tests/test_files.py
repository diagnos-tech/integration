"""🇺🇸 `/v1/drives/{sg}/nodes`: multipart upload reaches `Drive.upload` with the right bytes; download streams them back.

🇧🇷 `/v1/drives/{sg}/nodes`: upload multipart chega em `Drive.upload` com os
bytes certos; download os transmite de volta.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import FakeDiagnos


def test_upload_passes_the_exact_bytes_to_drive_upload(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 The multipart file body reaches `Drive.upload` byte-for-byte, with `name`/`mime_type`/`exam_id` intact.

    🇧🇷 O corpo multipart do arquivo chega em `Drive.upload` byte a byte, com `name`/`mime_type`/`exam_id` intactos.
    """
    payload = b"\x89PNG\r\n fake bytes for a drive node"

    response = client.post(
        "/v1/drives/sg1/nodes",
        files={"file": ("scan.png", payload, "image/png")},
        data={"exam_id": "exam_1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["security_group_id"] == "sg1"
    assert body["size"] == len(payload)

    drive = fake_vault.drives.drive("sg1")
    assert drive.last_upload is not None
    assert drive.last_upload["data"] == payload
    assert drive.last_upload["name"] == "scan.png"
    assert drive.last_upload["mime_type"] == "image/png"
    assert drive.last_upload["exam_id"] == "exam_1"


def test_download_content_streams_bytes_with_content_disposition(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `GET .../content` streams the exact uploaded bytes and names them in `Content-Disposition`.

    🇧🇷 `GET .../content` transmite exatamente os bytes enviados e os nomeia em `Content-Disposition`.
    """
    payload = b"some decrypted file content"
    upload = client.post("/v1/drives/sg1/nodes", files={"file": ("report.txt", payload, "text/plain")})
    node_id = upload.json()["node_id"]

    response = client.get(f"/v1/drives/sg1/nodes/{node_id}/content")

    assert response.status_code == 200
    assert response.content == payload
    assert "report.txt" in response.headers["content-disposition"]
    # 🇺🇸/🇧🇷 Starlette appends `; charset=utf-8` to any `text/*` media type on its own.
    assert response.headers["content-type"].startswith("text/plain")


def test_list_nodes_includes_the_decrypted_name(client: TestClient) -> None:
    """🇺🇸 `GET /v1/drives/{sg}/nodes` lists every uploaded node with its name decrypted alongside it.

    🇧🇷 `GET /v1/drives/{sg}/nodes` lista todo nó enviado com o nome decifrado junto.
    """
    client.post("/v1/drives/sg1/nodes", files={"file": ("chest_ct.dcm", b"dicom bytes", "application/dicom")})

    response = client.get("/v1/drives/sg1/nodes")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "chest_ct.dcm"
    assert items[0]["node"]["security_group_id"] == "sg1"


def test_get_node_returns_the_decrypted_name(client: TestClient) -> None:
    """🇺🇸 `GET .../nodes/{id}` reports the plaintext `name` alongside the sealed `DriveNode`.

    🇧🇷 `GET .../nodes/{id}` reporta o `name` em claro junto do `DriveNode` selado.
    """
    upload = client.post("/v1/drives/sg1/nodes", files={"file": ("chest_ct.dcm", b"dicom bytes", "application/dicom")})
    node_id = upload.json()["node_id"]

    response = client.get(f"/v1/drives/sg1/nodes/{node_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "chest_ct.dcm"
    assert body["node"]["node_id"] == node_id
