"""🇺🇸 `/v1/drives/{sg}/…`: uploads, folders, listing, reads scoped to the group in the path, safe downloads.

🇧🇷 `/v1/drives/{sg}/…`: uploads, pastas, listagem, leituras restritas ao
grupo do path, downloads seguros.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diagnos_api.routers.files import _content_disposition

from conftest import FakeDiagnos


def test_upload_passes_the_exact_bytes_to_drive_upload(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 The multipart body reaches `Drive.upload` byte-for-byte, with name/MIME/exam/folder intact.

    🇧🇷 O corpo multipart chega em `Drive.upload` byte a byte, com nome/MIME/exame/pasta intactos.
    """
    payload = b"\x89PNG\r\n fake bytes for a drive node"

    response = client.post(
        "/v1/drives/sg1/nodes",
        files={"file": ("scan.png", payload, "image/png")},
        data={"exam_id": "exam_1", "parent_id": "folder_1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["security_group_id"] == "sg1"
    assert body["size"] == len(payload)
    assert body["parent_id"] == "folder_1"
    assert fake_vault.drives.drive("sg1").calls == [
        (
            "upload",
            {
                "data": payload,
                "name": "scan.png",
                "mime_type": "image/png",
                "exam_id": "exam_1",
                "parent_id": "folder_1",
            },
        )
    ]


def test_an_explicit_mime_type_wins_over_the_part_header(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 A `mime_type` form field overrides the part's own `Content-Type` (browsers send `.dcm` as octet-stream).

    🇧🇷 Um campo `mime_type` sobrepõe o `Content-Type` da parte (navegadores mandam `.dcm` como octet-stream).
    """
    client.post(
        "/v1/drives/sg1/nodes",
        files={"file": ("ct.dcm", b"dicom", "application/octet-stream")},
        data={"mime_type": "application/dicom"},
    )

    _, upload = fake_vault.drives.drive("sg1").calls[0]
    assert upload["mime_type"] == "application/dicom"


def test_create_folder_returns_its_node_id(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `POST /v1/drives/{sg}/folders` creates the folder in `sg` and answers 201 with its node id.

    🇧🇷 `POST /v1/drives/{sg}/folders` cria a pasta em `sg` e responde 201 com o id do nó.
    """
    response = client.post("/v1/drives/sg1/folders", json={"name": "Tomografias", "parent_id": "folder_0"})

    assert response.status_code == 201
    node_id = response.json()["node_id"]
    assert fake_vault.drives.get(node_id).kind == "folder"
    assert fake_vault.drives.drive("sg1").calls == [("create_folder", {"name": "Tomografias", "parent_id": "folder_0"})]


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "x", "unknown": 1}, {}])
def test_create_folder_rejects_a_malformed_body(client: TestClient, body: dict[str, object]) -> None:
    """🇺🇸 An empty name, an unknown field or a missing name is a 422, never a folder.

    🇧🇷 Nome vazio, campo desconhecido ou nome ausente é um 422, nunca uma pasta.
    """
    assert client.post("/v1/drives/sg1/folders", json=body).status_code == 422


def test_list_nodes_includes_the_decrypted_name_and_forwards_filters(
    client: TestClient, fake_vault: FakeDiagnos
) -> None:
    """🇺🇸 Every node comes back with its name decrypted; exam, folder, pending and paging reach `Drive.list`.

    🇧🇷 Todo nó volta com o nome decifrado; exame, pasta, pendentes e paginação chegam em `Drive.list`.
    """
    client.post("/v1/drives/sg1/nodes", files={"file": ("chest_ct.dcm", b"dicom bytes", "application/dicom")})

    response = client.get(
        "/v1/drives/sg1/nodes",
        params={"exam_id": "exam_1", "parent_id": "folder_1", "include_pending": "true", "limit": 1, "cursor": "c1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [(item["name"], item["node"]["security_group_id"]) for item in body["items"]] == [("chest_ct.dcm", "sg1")]
    assert body["next_cursor"] == "cursor_2"
    assert fake_vault.drives.drive("sg1").calls[-1] == (
        "list",
        {"exam_id": "exam_1", "parent_id": "folder_1", "include_pending": True, "limit": 1, "cursor": "c1"},
    )


def test_a_group_without_a_key_lists_with_null_names_and_refuses_reads(
    client: TestClient, fake_vault: FakeDiagnos
) -> None:
    """🇺🇸 Listing degrades to `name: null` like document summaries; opening one file is the SDK's 403.

    🇧🇷 A listagem degrada para `name: null` como os resumos de documento; abrir um arquivo é o 403 do SDK.
    """
    node_id = client.post("/v1/drives/sg1/nodes", files={"file": ("a.txt", b"a", "text/plain")}).json()["node_id"]
    fake_vault.drives.drive("sg1").locked = True
    fake_vault.drives.locked = True

    listed = client.get("/v1/drives/sg1/nodes")
    opened = client.get(f"/v1/drives/sg1/nodes/{node_id}")

    assert listed.status_code == 200
    assert listed.json()["items"][0]["name"] is None
    assert opened.status_code == 403
    assert opened.json()["error"]["code"] == "group_key_unavailable"


@pytest.mark.parametrize("limit", [0, 201])
def test_list_limit_is_bounded(client: TestClient, limit: int) -> None:
    """🇺🇸 The page size stays within the vault's own 1..200. 🇧🇷 O tamanho da página fica no 1..200 do próprio cofre."""
    assert client.get("/v1/drives/sg1/nodes", params={"limit": limit}).status_code == 422


def test_get_node_returns_the_decrypted_name(client: TestClient) -> None:
    """🇺🇸 `GET .../nodes/{id}` reports the plaintext `name` alongside the sealed `DriveNode`.

    🇧🇷 `GET .../nodes/{id}` reporta o `name` em claro junto do `DriveNode` selado.
    """
    upload = client.post("/v1/drives/sg1/nodes", files={"file": ("chest_ct.dcm", b"dicom bytes", "application/dicom")})
    node_id = upload.json()["node_id"]

    response = client.get(f"/v1/drives/sg1/nodes/{node_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "chest_ct.dcm"
    assert response.json()["node"]["node_id"] == node_id


@pytest.mark.parametrize("suffix", ["", "/content"])
def test_a_node_of_another_group_is_not_found_under_this_one(client: TestClient, suffix: str) -> None:
    """🇺🇸 The vault reads by id alone; the route still refuses to serve `sg2`'s node under `sg1`'s path.

    🇧🇷 O cofre lê só pelo id; a rota ainda recusa servir o nó de `sg2` sob o path de `sg1`.
    """
    upload = client.post("/v1/drives/sg2/nodes", files={"file": ("other.txt", b"not yours", "text/plain")})
    node_id = upload.json()["node_id"]

    response = client.get(f"/v1/drives/sg1/nodes/{node_id}{suffix}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DriveNodeNotFound"


def test_an_unknown_node_is_the_vaults_404(client: TestClient) -> None:
    """🇺🇸 The vault's `DriveNodeNotFound` passes through as-is. 🇧🇷 O `DriveNodeNotFound` do cofre passa como está."""
    response = client.get("/v1/drives/sg1/nodes/node_missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DriveNodeNotFound"


def test_download_content_streams_bytes_with_content_disposition(client: TestClient) -> None:
    """🇺🇸 `GET .../content` streams the exact uploaded bytes and names them in `Content-Disposition`.

    🇧🇷 `GET .../content` transmite exatamente os bytes enviados e os nomeia em `Content-Disposition`.
    """
    payload = b"some decrypted file content"
    upload = client.post("/v1/drives/sg1/nodes", files={"file": ("report.txt", payload, "text/plain")})
    node_id = upload.json()["node_id"]

    response = client.get(f"/v1/drives/sg1/nodes/{node_id}/content")

    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-disposition"] == "attachment; filename=\"report.txt\"; filename*=UTF-8''report.txt"
    # 🇺🇸/🇧🇷 Starlette appends `; charset=utf-8` to any `text/*` media type on its own.
    assert response.headers["content-type"].startswith("text/plain")


def test_download_content_streams_zero_bytes_for_an_empty_file(client: TestClient) -> None:
    """🇺🇸 An empty upload downloads as an exact empty body, not a broken stream — `iter_download`'s edge case.

    `_FakeReading.iter_download` yields two chunks (`data[:half]`,
    `data[half:]`) mirroring the SDK's lazy decryptor; for `b""` that is two
    empty chunks, which `StreamingResponse` still has to turn into a valid
    zero-length `200`, not an empty/broken response.

    🇧🇷 Um upload vazio baixa como um corpo vazio exato, não um stream
    quebrado — o caso de borda de `iter_download`.

    `_FakeReading.iter_download` entrega dois pedaços (`data[:half]`,
    `data[half:]`) espelhando o decifrador preguiçoso do SDK; para `b""` isso
    são dois pedaços vazios, que o `StreamingResponse` ainda precisa virar um
    `200` de tamanho zero válido, não uma resposta vazia/quebrada.
    """
    upload = client.post("/v1/drives/sg1/nodes", files={"file": ("empty.txt", b"", "text/plain")})
    node_id = upload.json()["node_id"]
    assert upload.json()["size"] == 0

    response = client.get(f"/v1/drives/sg1/nodes/{node_id}/content")

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["content-disposition"].startswith('attachment; filename="empty.txt"')


def test_download_without_a_mime_type_is_octet_stream(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 A node with no recorded MIME type downloads as `application/octet-stream`.

    🇧🇷 Um nó sem tipo MIME registrado baixa como `application/octet-stream`.
    """
    node_id = fake_vault.drives.store.add("sg1", "blob", data=b"raw")

    response = client.get(f"/v1/drives/sg1/nodes/{node_id}/content")

    assert response.headers["content-type"] == "application/octet-stream"
    assert response.content == b"raw"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("exams/2024/scan.dcm", "attachment; filename=\"scan.dcm\"; filename*=UTF-8''scan.dcm"),
        ("..\\..\\evil.sh", "attachment; filename=\"evil.sh\"; filename*=UTF-8''evil.sh"),
        (
            'a"b\r\nSet-Cookie: x',
            "attachment; filename=\"a_b__Set-Cookie: x\"; filename*=UTF-8''a_b__Set-Cookie%3A%20x",
        ),
        ("laudo ção.pdf", "attachment; filename=\"laudo ??o.pdf\"; filename*=UTF-8''laudo%20%C3%A7%C3%A3o.pdf"),
        ("..", "attachment; filename=\"arquivo\"; filename*=UTF-8''arquivo"),
        ("folder/", "attachment; filename=\"arquivo\"; filename*=UTF-8''arquivo"),
    ],
)
def test_content_disposition_offers_only_a_safe_base_name(name: str, expected: str) -> None:
    """🇺🇸 Paths collapse to their last segment; quotes and CR/LF never reach the header; non-ASCII stays in `filename*`.

    🇧🇷 Caminhos viram o último segmento; aspas e CR/LF nunca chegam ao header; não-ASCII sobrevive em `filename*`.
    """
    assert _content_disposition(name) == expected
