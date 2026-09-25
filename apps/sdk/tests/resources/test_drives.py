"""🇺🇸 `Drives`/`Drive`: upload (single and multipart), download, naming.

🇧🇷 `Drives`/`Drive`: upload (single e multipart), download, nomeação.
"""

from __future__ import annotations

from diagnos.crypto import decrypt_bytes, derive_node_key, encrypted_size
from diagnos.models import DriveNode
from diagnos.resources.drives import Drive, Drives, UploadSource

from vault_double import Harness, harness  # noqa: F401 — `harness` is a fixture, used by name as a parameter


def _drive(harness: Harness, security_group_id: str = "sg1") -> Drive:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 A `Drive` for `security_group_id`, wired to `harness`.

    🇧🇷 Um `Drive` para `security_group_id`, conectado a `harness`.
    """
    drives = Drives(
        harness.transport, harness.keyring_provider, harness.entropy, workspace_id="ws_1", settings=harness.settings
    )
    return drives.drive(security_group_id)


def _stored_object_for(harness: Harness, node: DriveNode) -> bytes:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 The raw (still encrypted) R2 bytes behind one drive node.

    🇧🇷 Os bytes crus (ainda cifrados) do R2 por trás de um nó de drive.
    """
    return harness.vault._objects[f"https://r2.example.test/objects/{node.storage_path}"]  # noqa: SLF001 — test reaches into the fake's storage on purpose


def test_upload_single_bytes_is_readable_with_the_derived_node_key(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 A small `bytes` upload goes through the single-PUT path and the R2 object opens with `derive_node_key`.

    🇧🇷 Um upload pequeno de `bytes` segue o caminho de PUT único e o objeto no R2 abre com `derive_node_key`.
    """
    drive = _drive(harness)
    plaintext = b"hello world"

    node = drive.upload(plaintext, name="hello.txt", mime_type="text/plain")

    assert node.mode == "single"
    assert node.status == "ready"
    assert node.declared_size == encrypted_size(len(plaintext))

    group_dek = harness.keyring.group_key("sg1")
    node_key = derive_node_key(group_dek, node.node_id)
    stored = _stored_object_for(harness, node)
    assert decrypt_bytes(node_key, stored) == plaintext


def test_upload_single_put_content_length_matches_the_encrypted_body(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 The `content-length` on the single `PUT` is exactly the encrypted body's length.

    🇧🇷 O `content-length` do `PUT` único é exatamente o tamanho do corpo cifrado.
    """
    drive = _drive(harness)
    drive.upload(b"hello world", name="hello.txt")

    put_request = harness.vault.put_requests[-1]
    assert put_request.headers["content-length"] == str(len(put_request.content))


def test_download_reconstructs_the_original_bytes(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `download` decrypts a single-mode node back to the exact plaintext that was uploaded.

    🇧🇷 `download` decifra um nó single de volta ao texto claro exato que foi enviado.
    """
    drive = _drive(harness)
    plaintext = b"the quick brown fox jumps over the lazy dog"
    node = drive.upload(plaintext, name="fox.txt")

    downloaded = drive.download(node.node_id)

    assert downloaded == plaintext


def test_name_of_decrypts_the_encrypted_name(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `name_of` decrypts `encrypted_name` under the group DEK back to the original file name.

    🇧🇷 `name_of` decifra `encrypted_name` sob a DEK do grupo de volta ao nome de arquivo original.
    """
    drive = _drive(harness)
    node = drive.upload(b"data", name="report.pdf")

    assert drive.name_of(node) == "report.pdf"


def test_name_of_returns_none_without_a_name(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 A node uploaded without `name=` has no `encrypted_name`, so `name_of` is `None`.

    🇧🇷 Um nó enviado sem `name=` não tem `encrypted_name`, então `name_of` é `None`.
    """
    drive = _drive(harness)
    node = drive.upload(b"data")

    assert node.encrypted_name is None
    assert drive.name_of(node) is None


def test_upload_multipart_splits_signs_and_reassembles(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 A big-enough file forces the multipart path: several parts, each with an `ETag`, reassembled on `download`.

    Forcing `single_threshold`/`part_size` down to tiny values here is what
    lets this test exercise the real multipart machinery — signing parts in
    a batch, streaming `encrypt_stream` output into fixed-size parts, and
    completing with the `ETag` each `PUT` returned — without needing an
    actual 64 MiB file.

    🇧🇷 Um arquivo grande o bastante força o caminho multipart: várias
    partes, cada uma com `ETag`, remontadas no `download`.

    Forçar `single_threshold`/`part_size` para valores minúsculos aqui é o
    que permite a este teste exercitar a maquinaria real de multipart —
    assinar partes em lote, transformar a saída de `encrypt_stream` em
    partes de tamanho fixo, e completar com o `ETag` que cada `PUT` devolveu
    — sem precisar de um arquivo de 64 MiB de verdade.
    """
    harness.vault.single_threshold = 10
    harness.vault.part_size = 64
    drive = _drive(harness)
    plaintext = bytes(range(256)) * 4  # 🇺🇸/🇧🇷 1024 plaintext bytes, well past the framing overhead of one chunk

    completed_parts: list[dict] = []
    original_complete_multipart = harness.vault.complete_multipart

    def spying_complete_multipart(security_group_id: str, node_id: str, parts: list[dict]) -> dict:
        completed_parts.extend(parts)
        return original_complete_multipart(security_group_id, node_id, parts)

    harness.vault.complete_multipart = spying_complete_multipart  # type: ignore[method-assign]

    node = drive.upload(plaintext, name="video.bin", mime_type="application/octet-stream")

    assert node.mode == "multipart"
    assert node.status == "ready"
    assert node.part_count is not None
    assert node.part_count > 1

    # 🇺🇸/🇧🇷 one PUT (and one stored object) per part, each completed with the real `ETag` its own PUT returned
    part_urls = [
        url
        for url in harness.vault._objects
        if f"/parts/{node.node_id}/" in url  # noqa: SLF001 — test reaches into the fake's storage on purpose
    ]
    assert len(part_urls) == node.part_count
    assert [part["part_number"] for part in completed_parts] == list(range(1, node.part_count + 1))
    assert all(part["etag"] for part in completed_parts)
    assert len({part["etag"] for part in completed_parts}) == node.part_count  # 🇺🇸/🇧🇷 every part got its own ETag

    downloaded = drive.download(node.node_id)
    assert downloaded == plaintext


def test_upload_many_stages_the_whole_batch_in_one_call(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `upload_many` reserves every file in one `POST {base}/uploads` call, not one per file.

    🇧🇷 `upload_many` reserva todo arquivo numa única chamada `POST {base}/uploads`, não uma por arquivo.
    """
    drive = _drive(harness)
    original_stage_uploads = harness.vault.stage_uploads
    call_count = {"n": 0}

    def counting_stage_uploads(security_group_id: str, body: dict) -> dict:
        call_count["n"] += 1
        return original_stage_uploads(security_group_id, body)

    harness.vault.stage_uploads = counting_stage_uploads  # type: ignore[method-assign]

    nodes = drive.upload_many(
        [
            UploadSource(b"one", name="one.txt"),
            UploadSource(b"two", name="two.txt"),
            UploadSource(b"three", name="three.txt"),
        ]
    )

    assert call_count["n"] == 1
    assert len(nodes) == 3
    assert {drive.name_of(node) for node in nodes} == {"one.txt", "two.txt", "three.txt"}


def test_upload_many_with_an_exam_id_tags_every_node(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `exam_id` on `upload_many` applies to the whole batch, not just the first file.

    🇧🇷 `exam_id` em `upload_many` vale para o lote inteiro, não só o primeiro arquivo.
    """
    drive = _drive(harness)

    nodes = drive.upload_many([UploadSource(b"a"), UploadSource(b"b")], exam_id="exam_1")

    assert all(node.exam_id == "exam_1" for node in nodes)


def test_drive_list_only_returns_ready_nodes_by_default(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `list()` hides pending nodes unless `include_pending=True` (`docs/PROTOCOL.md §9`).

    🇧🇷 `list()` esconde nós pendentes a menos que `include_pending=True` (`docs/PROTOCOL.md §9`).
    """
    drive = _drive(harness)
    drive.upload(b"one")
    drive.upload(b"two")

    page = drive.list()

    assert len(page.items) == 2
    assert all(node.status == "ready" for node in page.items)


def test_iter_download_streams_the_same_plaintext_as_download(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `iter_download` yields exactly what `download` returns, one chunk at a time.

    🇧🇷 `iter_download` entrega exatamente o que `download` devolve, um pedaço por vez.
    """
    drive = _drive(harness)
    plaintext = bytes(range(256)) * 300
    node = drive.upload(plaintext, name="stream.bin")

    stream = drive.iter_download(node.node_id)
    assert hasattr(stream, "__next__")
    assert b"".join(stream) == drive.download(node.node_id) == plaintext
