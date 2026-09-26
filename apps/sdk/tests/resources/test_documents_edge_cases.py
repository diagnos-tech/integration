"""🇺🇸 `VersionedDocuments`: a document missing its own group's DEK, a summary-less index, and a draft that vanishes.

`test_documents.py` already drives the SDK's own `create`/`update`/`read`
end to end; this file is only about the defensive paths that a document
outside the SDK's control can put it in — a `FakeVault` index mutated
directly (a document created before `encrypted_index` existed, or one whose
`encrypted_keys` never carried its own group), and a genuine two-request
race inside `read()` itself (the draft the index pointed to is gone by the
time the second `GET` for it lands).

🇧🇷 `VersionedDocuments`: um documento sem a própria DEK de grupo, um índice
sem resumo, e um rascunho que desaparece.

`test_documents.py` já roda `create`/`update`/`read` do próprio SDK ponta a
ponta; este arquivo é só sobre os caminhos defensivos em que um documento
fora do controle do SDK pode colocá-lo — um índice de `FakeVault` mutado
direto (um documento criado antes de `encrypted_index` existir, ou um cujo
`encrypted_keys` nunca carregou o próprio grupo), e uma corrida de verdade
entre duas requisições dentro do próprio `read()` (o rascunho que o índice
apontava sumiu quando o segundo `GET` dele chega).
"""

from __future__ import annotations

import pytest
from diagnos.crypto import DOCUMENT_DEK_INFO, derive_content_key, unwrap_key
from diagnos.crypto.content import DRAFT_CONTENT_INFO, seal_bytes
from diagnos.crypto.secure import SecretBox
from diagnos.errors import CryptoError
from diagnos.models import DocumentIndex, PatientRecord, PatientSummary
from diagnos.resources._documents import VersionedDocuments

from vault_double import Harness, harness, make_documents  # noqa: F401 — `harness` is a fixture

_JANE = PatientRecord(legal_name="Jane Doe", display_name="Jane", external_id="mrn-1")


def _patients(h: Harness) -> VersionedDocuments[PatientRecord, PatientSummary]:
    """🇺🇸 The engine for `patients` (two streams). 🇧🇷 O motor de `patients` (dois fluxos)."""
    return make_documents(h, resource="patients", record_model=PatientRecord, summary_model=PatientSummary)


def test_read_raises_crypto_error_when_the_index_has_no_dek_for_its_own_group(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A document whose `encrypted_keys` lost its own security group is unreadable, `CryptoError`, not a `KeyError`.

    This mirrors `resources/drives`'s `test_a_node_without_its_group_key_fails_closed`
    for the document side: the map itself, not the caller's own keyring, is
    what is missing the entry.

    🇧🇷 Um documento cujo `encrypted_keys` perdeu o próprio security group é
    ilegível, `CryptoError`, não um `KeyError`.

    Isto espelha, do lado de documentos, o
    `test_a_node_without_its_group_key_fails_closed` de `resources/drives`:
    o próprio mapa, não o keyring de quem chama, é quem está sem a entrada.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    harness.vault._documents[("patients", document_id)]["encrypted_keys"] = {}  # noqa: SLF001 — simulating a corrupt index

    with pytest.raises(CryptoError, match=document_id):
        documents.read(document_id)


def test_list_and_read_leave_the_summary_none_for_a_document_with_no_encrypted_index(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A document without `encrypted_index` (predates the field) reads with `summary=None`, never a crash.

    🇧🇷 Um documento sem `encrypted_index` (anterior ao campo existir) lê com `summary=None`, nunca uma quebra.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    del harness.vault._documents[("patients", document_id)]["encrypted_index"]  # noqa: SLF001

    opened = documents.read(document_id)
    (row,) = [item for item in documents.list().items if item.index.document_id == document_id]

    assert opened.summary is None
    assert row.summary is None
    assert (
        opened.record.legal_name == "Jane Doe"
    )  # 🇺🇸/🇧🇷 the record itself still opens fine · o registro em si ainda abre


def _dek(h: Harness, index: DocumentIndex) -> SecretBox:
    """🇺🇸 The document DEK, unwrapped independently of the engine. 🇧🇷 A DEK do documento, aberta sem o motor."""
    group_key = h.keyring.group_key(index.security_group_id)
    return unwrap_key(group_key, index.encrypted_keys[index.security_group_id], DOCUMENT_DEK_INFO)


def _seed_patient_draft(h: Harness, index: DocumentIndex, record: PatientRecord) -> None:
    """🇺🇸 Seals `record` as the web editor's autosave would, and stores it as the `data` draft.

    Duplicated from `test_documents.py` on purpose: each test file is a
    self-contained unit, per this package's own convention (see
    `vault_double.py`'s module docstring on the bare-import fixture pattern).

    🇧🇷 Duplicado de `test_documents.py` de propósito: cada arquivo de teste é
    uma unidade autocontida, seguindo a própria convenção do pacote (veja a
    docstring de `vault_double.py` sobre o padrão de fixture de import direto).
    """
    document_id = index.document_id
    context = h.vault.security_context("patients", document_id, "draft:data")["value"]
    key = derive_content_key(_dek(h, index), "draft:data", context)
    sealed = seal_bytes(key, record.model_dump_json(exclude_none=True).encode(), DRAFT_CONTENT_INFO)
    h.vault.seed_draft("patients", document_id, sealed)


def test_read_falls_back_to_the_committed_version_when_the_draft_vanishes_mid_read(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 A draft discarded between `read()`'s index fetch and its own draft fetch is not fatal.

    `read()` decides to fetch the draft from what the *index* said
    (`draft_is_newer`); if the draft is gone by the time the second `GET`
    for it lands — a real race, the web editor discarding it in between —
    the vault answers `null` and `read()` must fall back to the latest
    committed version instead of blowing up on a `None` where it expected a
    dict.

    🇧🇷 Um rascunho descartado entre a busca do índice de `read()` e a busca
    do próprio rascunho não é fatal.

    `read()` decide buscar o rascunho a partir do que o *índice* disse
    (`draft_is_newer`); se o rascunho já não existe quando o segundo `GET`
    dele chega — uma corrida de verdade, o editor web descartando-o no meio
    — o cofre responde `null` e `read()` precisa cair para a última versão
    confirmada em vez de quebrar num `None` onde esperava um dict.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    _seed_patient_draft(harness, created.index, _JANE.model_copy(update={"display_name": "typing…"}))

    real_get = harness.transport.get
    calls = {"n": 0}

    def get_then_vanish(path: str, *, query: dict[str, object] | None = None, signed: bool = True) -> object:
        result = real_get(path, query=query, signed=signed)
        calls["n"] += 1
        if calls["n"] == 1:
            # 🇺🇸/🇧🇷 discard the draft right after the index says it's newer, before the draft GET lands.
            harness.vault._documents[("patients", document_id)]["streams"]["data"]["draft"] = None  # noqa: SLF001
        return result

    monkeypatch.setattr(harness.transport, "get", get_then_vanish)

    opened = documents.read(document_id)

    assert opened.version_id == created.index.latest_version_id
    assert opened.draft_rev is None
    assert opened.record.display_name == "Jane"  # 🇺🇸/🇧🇷 the committed record, not the vanished draft
