"""🇺🇸 `VersionedDocuments`: the generic CRUD engine, exercised directly (not through `Patients`/`Exams`).

🇧🇷 `VersionedDocuments`: o motor genérico de CRUD, exercitado direto (não via `Patients`/`Exams`).
"""

from __future__ import annotations

import json

import pytest
from diagnos.crypto import DEK_INFO, RECORD_INFO, EncryptedPayload, decrypt_content, unwrap_key
from diagnos.models import PatientRecord
from diagnos.session.keyring import GroupKeyUnavailable

from vault_double import (  # noqa: F401 — `harness`/`sse_c_harness` are fixtures, used by name as parameters
    Harness,
    harness,
    make_documents,
    sse_c_harness,
)

_SSE_C_HEADERS = (
    "x-amz-server-side-encryption-customer-algorithm",
    "x-amz-server-side-encryption-customer-key",
    "x-amz-server-side-encryption-customer-key-md5",
)


def _object_bytes(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    document_id: str,
    version_id: str,
) -> bytes:
    """🇺🇸 Reads the raw R2 object a given document version was stored under.

    🇧🇷 Lê o objeto cru do R2 sob o qual uma dada versão de documento foi guardada.
    """
    key = f"doc/patients/{document_id}/{version_id}"
    return harness.vault._objects[f"https://r2.example.test/objects/{key}"]  # noqa: SLF001 — test reaches into the fake's storage on purpose


def test_create_writes_an_object_openable_with_the_wrapped_dek(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 The R2 object is `{salt,nonce,ciphertext}`, decryptable with the DEK wrapped in `encrypted_keys`.

    🇧🇷 O objeto no R2 é `{salt,nonce,ciphertext}`, decifrável com a DEK embrulhada em `encrypted_keys`.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    record = PatientRecord(legal_name="Jane Doe", display_name="Jane")

    index = documents.create(record, security_groups=["sg1"])

    assert index.security_groups == ["sg1"]
    assert index.latest_version_id is not None
    raw = _object_bytes(harness, index.document_id, index.latest_version_id)
    payload = EncryptedPayload.from_dict(json.loads(raw))

    group_dek = harness.keyring.group_key("sg1")
    doc_dek = unwrap_key(group_dek, index.encrypted_keys["sg1"], DEK_INFO["patients"])
    plaintext = decrypt_content(doc_dek, payload, RECORD_INFO["patients"])
    assert PatientRecord.model_validate_json(plaintext) == record


def test_create_put_content_length_matches_the_body(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 The `content-length` header on the `PUT` is exactly `len(body)`, never a guess.

    🇧🇷 O header `content-length` do `PUT` é exatamente `len(body)`, nunca um palpite.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    documents.create(PatientRecord(legal_name="Jane Doe", display_name="Jane"), security_groups=["sg1"])

    put_request = harness.vault.put_requests[-1]
    assert put_request.headers["content-length"] == str(len(put_request.content))


def test_read_decrypts_the_record(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 `read` round-trips a created record byte-for-byte through the encrypted object.

    🇧🇷 `read` faz o registro criado ir e voltar, byte a byte, pelo objeto cifrado.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    record = PatientRecord(legal_name="Jane Doe", display_name="Jane", email="jane@example.test")
    created = documents.create(record, security_groups=["sg1"])

    index, read_record = documents.read(created.document_id)

    assert index.document_id == created.document_id
    assert read_record == record


def test_update_creates_a_new_version_reusing_the_document_dek(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 `update` encrypts a brand new version, but under the *same* `doc_dek` as `create`.

    🇧🇷 `update` cifra uma versão nova, mas sob a *mesma* `doc_dek` de `create`.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    original = PatientRecord(legal_name="Jane Doe", display_name="Jane")
    created = documents.create(original, security_groups=["sg1"])
    original_dek = unwrap_key(harness.keyring.group_key("sg1"), created.encrypted_keys["sg1"], DEK_INFO["patients"])

    updated_record = original.model_copy(update={"display_name": "Jane D."})
    updated = documents.update(created.document_id, updated_record)

    assert updated.document_id == created.document_id
    assert updated.latest_version_id != created.latest_version_id
    assert len(updated.versions) == 2
    updated_dek = unwrap_key(harness.keyring.group_key("sg1"), updated.encrypted_keys["sg1"], DEK_INFO["patients"])
    assert updated_dek == original_dek

    _, reread = documents.read(created.document_id)
    assert reread.display_name == "Jane D."


def test_list_paginates_by_next_cursor(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 `list`/`iter_all` walk every created document, exactly once each, across pages.

    🇧🇷 `list`/`iter_all` percorrem todo documento criado, uma única vez cada, por várias páginas.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    for i in range(5):
        documents.create(PatientRecord(legal_name=f"Patient {i}", display_name=f"P{i}"), security_groups=["sg1"])

    first_page = documents.list(limit=2)
    assert len(first_page.items) == 2
    assert first_page.next_cursor is not None

    second_page = documents.list(limit=2, cursor=first_page.next_cursor)
    assert len(second_page.items) == 2

    seen_ids = {item.document_id for item in first_page} | {item.document_id for item in second_page}
    assert len(seen_ids) == 4  # 🇺🇸/🇧🇷 two pages of two, no repeats

    all_ids = [index.document_id for index in documents.iter_all(limit=2)]
    assert len(all_ids) == 5
    assert len(set(all_ids)) == 5


def test_delete_marks_is_deleted_via_a_new_version_and_keeps_the_content(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 `delete` is a new version with `is_deleted=True` — the record itself survives, re-encrypted.

    🇧🇷 `delete` é uma versão nova com `is_deleted=True` — o registro em si sobrevive, recifrado.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    created = documents.create(PatientRecord(legal_name="Jane Doe", display_name="Jane"), security_groups=["sg1"])

    deleted = documents.delete(created.document_id)

    assert deleted.is_deleted is True
    assert deleted.latest_version_id != created.latest_version_id
    _, record = documents.read(created.document_id)
    assert record.legal_name == "Jane Doe"


def test_archive_then_unarchive_round_trips_the_flag(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 `archive` then `unarchive` leaves `is_archived` back at `False`, across two more versions.

    🇧🇷 `archive` seguido de `unarchive` deixa `is_archived` de volta em `False`, em mais duas versões.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    created = documents.create(PatientRecord(legal_name="Jane Doe", display_name="Jane"), security_groups=["sg1"])

    archived = documents.archive(created.document_id)
    assert archived.is_archived is True

    unarchived = documents.unarchive(created.document_id)
    assert unarchived.is_archived is False
    assert len(unarchived.versions) == 3


def test_read_raises_group_key_unavailable_when_the_keyring_lost_the_group(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 A document readable at creation time becomes unreadable the moment its group DEK is gone.

    🇧🇷 Um documento legível na criação fica ilegível assim que a DEK do grupo dele some.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    created = documents.create(PatientRecord(legal_name="Jane Doe", display_name="Jane"), security_groups=["sg1"])

    # 🇺🇸 Simulates a later enrollment approved for a narrower set of groups.
    # 🇧🇷 Simula um enrollment posterior aprovado para um conjunto mais estreito de grupos.
    del harness.keyring.group_keys["sg1"]

    with pytest.raises(GroupKeyUnavailable):
        documents.read(created.document_id)


def test_sse_c_adds_the_three_headers_on_put_and_get(
    sse_c_harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 With `settings.sse_c` on, every PUT/GET against R2 carries the three SSE-C headers.

    🇧🇷 Com `settings.sse_c` ligado, todo PUT/GET contra o R2 carrega os três headers de SSE-C.
    """
    documents = make_documents(sse_c_harness, resource="patients", record_model=PatientRecord)
    created = documents.create(PatientRecord(legal_name="Jane Doe", display_name="Jane"), security_groups=["sg1"])

    put_headers = sse_c_harness.vault.put_requests[-1].headers
    for header in _SSE_C_HEADERS:
        assert header in put_headers

    documents.read(created.document_id)
    get_headers = sse_c_harness.vault.get_requests[-1].headers
    for header in _SSE_C_HEADERS:
        assert header in get_headers


def test_sse_c_off_by_default_adds_no_extra_headers(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 Without `settings.sse_c`, no SSE-C header is ever sent (`docs/PROTOCOL.md §10`'s opt-in default).

    🇧🇷 Sem `settings.sse_c`, nenhum header de SSE-C é mandado (padrão opt-in de `docs/PROTOCOL.md §10`).
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord)
    documents.create(PatientRecord(legal_name="Jane Doe", display_name="Jane"), security_groups=["sg1"])

    put_headers = harness.vault.put_requests[-1].headers
    for header in _SSE_C_HEADERS:
        assert header not in put_headers
