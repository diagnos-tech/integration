"""🇺🇸 Every resource call asks for the keyring before its first signed request, so it can be a program's first call.

`Diagnos` unlocks lazily inside the keyring provider; a resource that signed
a request before asking for the keyring would fail with
`SessionExpiredError` on a fresh client instead of unlocking. The session
here exists only once the provider has been asked, exactly as with a real
`Diagnos` before its first `unlock()`.

🇧🇷 Toda chamada de recurso pede o keyring antes da primeira requisição assinada: pode ser a primeira do programa.

O `Diagnos` desbloqueia de forma preguiçosa dentro do provedor de keyring;
um recurso que assinasse uma requisição antes de pedir o keyring falharia com
`SessionExpiredError` num cliente novo em vez de desbloquear. A sessão aqui só
existe depois de o provedor ser consultado, exatamente como num `Diagnos` de
verdade antes do primeiro `unlock()`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from diagnos.models import PatientRecord, PatientSummary
from diagnos.resources._documents import VersionedDocuments
from diagnos.resources.drives import Drives
from diagnos.session.keyring import Keyring
from diagnos.transport.http import VaultTransport
from diagnos.transport.token import ServiceAccountToken

from vault_double import VAULT_URL, WORKSPACE_ID, Harness, harness  # noqa: F401 — `harness` is a fixture


class _LazySession:
    """🇺🇸 A session that appears only once the keyring was asked for — `Diagnos`'s lazy unlock, in miniature.

    🇧🇷 Uma sessão que só aparece depois de o keyring ser pedido — o unlock preguiçoso do `Diagnos`, em miniatura.
    """

    def __init__(self, keyring: Keyring) -> None:
        """🇺🇸 Starts locked. 🇧🇷 Começa travada."""
        self._keyring = keyring
        self.unlocked = False

    def keyring_provider(self) -> Keyring:
        """🇺🇸 Unlocks, then hands out the keyring. 🇧🇷 Desbloqueia, depois entrega o keyring."""
        self.unlocked = True
        return self._keyring

    def lock(self) -> None:
        """🇺🇸 Back to no session. 🇧🇷 De volta a sem sessão."""
        self.unlocked = False


def _wire(h: Harness) -> tuple[_LazySession, VersionedDocuments[PatientRecord, PatientSummary], Drives]:
    """🇺🇸 A transport that signs only once the session unlocked. 🇧🇷 Um transporte que só assina depois do unlock."""
    lazy = _LazySession(h.keyring)
    token = ServiceAccountToken(
        raw="apikey-test", key_id="key_1", account_id="acc_1", workspace_id=WORKSPACE_ID, name="svc@ws_1"
    )
    transport = VaultTransport(
        h.settings,
        token,
        session_keys=lambda: h.keyring.session if lazy.unlocked else None,
        client=httpx.Client(transport=httpx.MockTransport(h.vault.handle_api), base_url=VAULT_URL),
        storage_client=httpx.Client(transport=httpx.MockTransport(h.vault.handle_storage)),
        sleep=lambda _seconds: None,
    )
    documents = VersionedDocuments(
        transport,
        lazy.keyring_provider,
        h.entropy,
        workspace_id=WORKSPACE_ID,
        resource="patients",
        record_model=PatientRecord,
        summary_model=PatientSummary,
    )
    return lazy, documents, Drives(transport, lazy.keyring_provider, h.entropy, workspace_id=WORKSPACE_ID)


_Call = Callable[[VersionedDocuments[PatientRecord, PatientSummary], Drives, dict[str, Any]], object]
CALLS: dict[str, _Call] = {
    "documents.list": lambda docs, drives, ids: docs.list(),
    "documents.read": lambda docs, drives, ids: docs.read(ids["document"]),
    "documents.update": lambda docs, drives, ids: docs.update(
        ids["document"], PatientRecord(legal_name="B", display_name="B"), summary=lambda current: PatientSummary()
    ),
    "documents.set_flags": lambda docs, drives, ids: docs.set_flags(ids["document"], is_archived=True),
    "drives.list": lambda docs, drives, ids: drives.list(),
    "drives.get": lambda docs, drives, ids: drives.get(ids["node"]),
    "drives.download": lambda docs, drives, ids: drives.download(ids["node"]),
}


@pytest.mark.parametrize("name", sorted(CALLS))
def test_a_locked_client_unlocks_on_its_first_call(harness: Harness, name: str) -> None:  # noqa: F811
    """🇺🇸 No `SessionExpiredError`: the call unlocks first. 🇧🇷 Sem `SessionExpiredError`: desbloqueia antes."""
    lazy, documents, drives = _wire(harness)
    record = PatientRecord(legal_name="A", display_name="A")
    document = documents.create(record, security_group="sg1", summary=PatientSummary.of(record, []))
    node = drives.drive("sg1").upload(b"bytes", name="a.txt")
    lazy.lock()

    CALLS[name](documents, drives, {"document": document.index.document_id, "node": node.node_id})
    assert lazy.unlocked
