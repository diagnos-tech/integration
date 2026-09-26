"""🇺🇸 `VersionedDocuments`: list, update and the archive/delete flags — the other half of `test_documents.py`.

Split out purely to keep both files under the line-count ceiling; the create/paths/read half lives in
`test_documents.py`, and both share `_documents_common.py`'s engine builders and request-inspection
helpers so nothing here duplicates them.

🇧🇷 `VersionedDocuments`: listagem, atualização e as flags de arquivar/apagar — a outra metade de `test_documents.py`.

Separado por causa apenas do teto de linhas; a metade de criação/paths/leitura mora em
`test_documents.py`, e os dois compartilham os construtores de motor e os auxiliares de inspeção de
requisição de `_documents_common.py`, então nada aqui os duplica.
"""

from __future__ import annotations

import httpx
import pytest
from diagnos.errors import ConflictError, ProtocolError, VaultError
from diagnos.models import PatientRecord, PatientSummary

from _documents_common import _JANE, _dek, _json_bodies, _patients
from vault_double import Harness, harness  # noqa: F401 — `harness` is a fixture, used by name as a parameter

# -- list --------------------------------------------------------------------


def test_list_decrypts_summaries_and_paginates(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Every row carries its summary; `iter_all` walks every page once.

    🇧🇷 Toda linha traz o resumo; `iter_all` passa uma vez.
    """
    documents = _patients(harness)
    for i in range(5):
        record = PatientRecord(legal_name=f"Patient {i}", display_name=f"P{i}")
        documents.create(record, security_group="sg1", summary=PatientSummary.of(record, []))

    first = documents.list(limit=2)
    names = [item.summary.display_name for item in documents.iter_all(limit=2) if item.summary is not None]

    assert len(first.items) == 2
    assert first.next_cursor is not None
    assert sorted(names) == [f"P{i}" for i in range(5)]
    assert not harness.vault.get_requests  # 🇺🇸/🇧🇷 no version downloaded · nenhuma versão baixada


def test_list_leaves_summary_empty_when_the_group_key_is_missing(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A row from a group without a key keeps `summary=None` instead of failing the page.

    🇧🇷 Uma linha de um grupo sem chave fica com `summary=None` em vez de derrubar a página.
    """
    documents = _patients(harness)
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    documents.create(_JANE, security_group="sg2", summary=PatientSummary.of(_JANE, []))
    del harness.keyring.group_keys["sg2"]

    by_group = {item.index.security_group_id: item.summary for item in documents.list()}

    assert by_group["sg1"] is not None
    assert by_group["sg2"] is None


def test_list_sends_the_filters(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `security_group`/`include_deleted` become the vault's query. 🇧🇷 Os filtros viram a query do cofre."""
    documents = _patients(harness)
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))

    page = documents.list(security_group="sg2", include_deleted=True)

    query = harness.vault.api_requests[-1].url.params
    assert query["security_group_id"] == "sg2"
    assert query["include_deleted"] == "true"
    assert page.items == []


# -- update ------------------------------------------------------------------


def test_update_reuses_the_dek_and_carries_the_summary_forward(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Same DEK, a second version, and the summary callback sees the current summary.

    🇧🇷 Mesma DEK, uma segunda versão, e o callback de resumo vê o resumo atual.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, ["vip"]))
    seen: list[PatientSummary | None] = []
    renamed = _JANE.model_copy(update={"display_name": "Jane D."})

    def summary(current: PatientSummary | None) -> PatientSummary:
        """🇺🇸 Records what the engine passed in, then carries the current tags forward.

        🇧🇷 Registra o que o motor passou, depois carrega as tags atuais adiante.
        """
        seen.append(current)
        return PatientSummary.of(renamed, current.tags if current else [])

    updated = documents.update(created.index.document_id, renamed, summary=summary)

    assert seen[0] is not None
    assert seen[0].tags == ["vip"]
    assert len(updated.index.versions) == 2
    assert _dek(harness, updated.index) == _dek(harness, created.index)
    assert documents.read(created.index.document_id).summary == PatientSummary.of(renamed, ["vip"])


def test_update_sends_the_conflict_guard_and_surfaces_a_mismatch(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `expected_latest_version_id` reaches the vault; a stale one is a `ConflictError`.

    🇧🇷 `expected_latest_version_id` chega ao cofre; um desatualizado vira `ConflictError`.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    stale = created.index.latest_version_id
    documents.update(created.index.document_id, _JANE, summary=lambda c: c or PatientSummary())

    with pytest.raises(ConflictError) as raised:
        documents.update(
            created.index.document_id,
            _JANE,
            summary=lambda c: c or PatientSummary(),
            expected_latest_version_id=stale,
        )

    assert raised.value.code == "DocumentVersionMismatch"
    assert _json_bodies(harness, "POST", "/streams/data/versions")[-1]["expected_latest_version_id"] == stale


def test_update_retries_briefly_while_another_writer_holds_the_pending_slot(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 `DocumentVersionPending` is retried (1.5 s, 3 s) like the web app, then surfaced.

    🇧🇷 `DocumentVersionPending` é retentado (1,5 s, 3 s) como o app web, depois exposto.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    harness.vault.stage_version("patients", document_id, "data", {"content_length": 100})  # 🇺🇸/🇧🇷 another writer

    with pytest.raises(ConflictError) as raised:
        documents.update(document_id, _JANE, summary=lambda c: c or PatientSummary())
    assert raised.value.code == "DocumentVersionPending"
    assert harness.sleeps == [1.5, 3.0]

    harness.sleeps.clear()
    real = harness.vault.stage_version
    calls = {"n": 0}

    def clears_after_one_refusal(*args: object) -> dict[str, object]:
        """🇺🇸 Lets the first stage call fail as usual, then clears the slot the other writer held.

        🇧🇷 Deixa a primeira chamada de stage falhar como de costume, depois libera o slot do outro escritor.
        """
        calls["n"] += 1
        if calls["n"] == 1:
            return real(*args)  # type: ignore[arg-type]
        harness.vault._pending.clear()  # noqa: SLF001 — the other writer's slot expired
        return real(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(harness.vault, "stage_version", clears_after_one_refusal)
    documents.update(document_id, _JANE, summary=lambda c: c or PatientSummary())
    assert harness.sleeps == [1.5]


def test_commit_is_retried_across_server_failures(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A commit lost to 5xx is replayed with backoff; after three attempts the error surfaces.

    🇧🇷 Um commit perdido em 5xx é reenviado com backoff; depois de três tentativas o erro aparece.
    """
    documents = _patients(harness)
    # 🇺🇸 The transport itself retries a 5xx once, so each engine attempt consumes two failures.
    # 🇧🇷 O transporte já retenta um 5xx uma vez, então cada tentativa do motor consome duas falhas.
    harness.vault.fail_next_commits = 4
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    assert harness.sleeps == [0.5, 1.0]

    harness.sleeps.clear()
    harness.vault.fail_next_commits = 6
    with pytest.raises(VaultError) as raised:
        documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    assert raised.value.status == 503
    assert harness.sleeps == [0.5, 1.0]


def test_commit_is_retried_after_a_network_error(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 A dropped connection on commit is replayed; a 4xx is not. 🇧🇷 Conexão caída no commit é reenviada; 4xx não."""
    documents = _patients(harness)
    real = harness.vault.commit_version
    drops = {"left": 1}

    def flaky(*args: object) -> dict[str, object]:
        """🇺🇸 Drops the connection once, then behaves — a transient network failure on commit.

        🇧🇷 Derruba a conexão uma vez, depois se comporta — uma falha de rede transitória no commit.
        """
        if drops["left"]:
            drops["left"] -= 1
            raise httpx.ConnectError("connection reset")
        return real(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(harness.vault, "commit_version", flaky)
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    assert harness.sleeps == [0.5]


def test_update_refuses_a_patch_only_answer(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """🇺🇸 A version reservation answered as patch-only breaks the contract.

    🇧🇷 Reserva respondida só-patch quebra o contrato.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    monkeypatch.setattr(
        harness.vault,
        "stage_version",
        lambda resource, document_id, _stream, _body: {"staged": False, "document": {}},
    )

    with pytest.raises(ProtocolError):
        documents.update(created.index.document_id, _JANE, summary=lambda c: c or PatientSummary())


# -- flags -------------------------------------------------------------------


def test_flags_are_patch_only(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Archive/delete send only the flag: no `content_length`, no new version, no upload.

    🇧🇷 Arquivar/apagar mandam só a flag: sem `content_length`, sem versão nova, sem upload.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    uploads = len(harness.vault.put_requests)

    archived = documents.set_flags(document_id, is_archived=True)
    deleted = documents.set_flags(document_id, is_deleted=True)
    restored = documents.set_flags(document_id, is_archived=False, is_deleted=False)

    assert archived.is_archived is True
    assert deleted.is_deleted is True
    assert (restored.is_archived, restored.is_deleted) == (False, False)
    assert len(restored.versions) == 1
    assert len(harness.vault.put_requests) == uploads
    assert _json_bodies(harness, "POST", "/streams/data/versions") == [
        {"is_archived": True},
        {"is_deleted": True},
        {"is_archived": False, "is_deleted": False},
    ]
