"""Wiring a `FakeVault` to a real `VaultTransport`: the `harness` fixture every test starts from.

Also the session keys and `Keyring` behind it. `Keyring`s here are built by hand with known group
keys — the whole point of `resources/` is that it never invents keys of its own.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import TypeVar

import httpx
import pytest
from pydantic import BaseModel

from diagnos.crypto import EntropyMixer
from diagnos.crypto.secure import SecretBox
from diagnos.models import ResourceKind
from diagnos.resources._documents import VersionedDocuments
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.token import ServiceAccountToken

from ._core import FakeVault
from ._wire import VAULT_URL, WORKSPACE_ID

RecordT = TypeVar("RecordT", bound=BaseModel)
SummaryT = TypeVar("SummaryT", bound=BaseModel)


def _fresh_session_keys() -> SessionKeys:
    """A session valid far into the future — none of these tests exercise expiry.

    Each key is born as its own `SecretBox` (`from_bytes` on a fresh
    `bytearray`, not a `bytes` literal) so the box holds the only copy — no
    caller can zero the underlying buffer out from under a later `as_secret`.
    """
    return SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        enc_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        expires_at=9_999_999_999,
    )


def make_keyring(group_deks: dict[str, bytes]) -> Keyring:
    """A `Keyring` holding exactly the group DEKs a test supplies — no enrollment, no network.

    Each DEK becomes its own `SecretBox`, born from a copy of the input
    bytes (`bytearray(dek)`) so the caller's own `bytes` — often reused
    across assertions in the same test — is never the buffer that gets
    zeroed.
    """
    return Keyring(
        enrollment_id="enroll_1",
        session=_fresh_session_keys(),
        group_keys={sg: SecretBox.from_bytes(bytearray(dek)) for sg, dek in group_deks.items()},
    )


@dataclass
class Harness:
    """Everything a `resources/` test needs: the fake backend, a live `VaultTransport`, entropy, keyring."""

    vault: FakeVault
    transport: VaultTransport
    entropy: EntropyMixer
    keyring: Keyring
    settings: Settings
    sleeps: list[float] = field(default_factory=list)

    def keyring_provider(self) -> Keyring:
        """The callable shape `VersionedDocuments`/`Drive` expect for `keyring_provider`."""
        return self.keyring


def _default_group_deks() -> dict[str, bytes]:
    """Two named security groups with fresh, independent DEKs.

    A plain function, not a fixture: `harness` is the only fixture a test
    file needs to import (the bare-import convention — see the module
    docstring), and it calls this on its own rather than depending on a
    `group_deks` fixture that a test module importing only `harness` would
    never register.
    """
    return {"sg1": secrets.token_bytes(32), "sg2": secrets.token_bytes(32)}


@pytest.fixture
def harness() -> Harness:
    """A ready-to-use `Harness`."""
    return _build_harness(_default_group_deks())


def _build_harness(group_deks: dict[str, bytes]) -> Harness:
    """Wires a fresh `FakeVault` to a real `VaultTransport` over `httpx.MockTransport`."""
    vault = FakeVault()
    keyring = make_keyring(group_deks)
    settings = Settings(api_token="apikey-test", vault_url=VAULT_URL)  # noqa: S106 — test fixture, not a real secret
    api_client = httpx.Client(transport=httpx.MockTransport(vault.handle_api), base_url=VAULT_URL)
    storage_client = httpx.Client(transport=httpx.MockTransport(vault.handle_storage))
    entropy = EntropyMixer()
    transport = VaultTransport(
        settings,
        _token(),
        session_keys=lambda: keyring.session,
        client=api_client,
        storage_client=storage_client,
        sleep=lambda _seconds: None,
    )
    return Harness(vault=vault, transport=transport, entropy=entropy, keyring=keyring, settings=settings)


def _token() -> ServiceAccountToken:
    """A `ServiceAccountToken` for `WORKSPACE_ID`, built without a real JWT."""
    return ServiceAccountToken(
        raw="apikey-test",
        key_id="key_1",
        account_id="acc_1",
        workspace_id=WORKSPACE_ID,
        name=f"svc@{WORKSPACE_ID}.diagnos.health",
    )


def make_documents(
    harness: Harness, *, resource: ResourceKind, record_model: type[RecordT], summary_model: type[SummaryT]
) -> VersionedDocuments[RecordT, SummaryT]:
    """A `VersionedDocuments` wired to `harness`, with a no-op `sleep` so retries cost no wall time."""
    return VersionedDocuments(
        harness.transport,
        harness.keyring_provider,
        harness.entropy,
        workspace_id=WORKSPACE_ID,
        resource=resource,
        record_model=record_model,
        summary_model=summary_model,
        sleep=harness.sleeps.append,
    )
