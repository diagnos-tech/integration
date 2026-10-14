"""`OpenBaoStore`: save/restore round-trips, expiry, absence, and the missing-`hvac` message.

The fake `hvac` client below only implements the three KV v2 calls
`OpenBaoStore` actually makes — it is not a mock of `hvac` itself, it is an
in-memory stand-in for OpenBao's own storage, so a bug in *what*
`OpenBaoStore` writes or reads shows up the same way it would against a real
server. `hvac.exceptions.InvalidPath` is the real exception class (`hvac`
is a dev dependency of this package), exactly what a real server raises for
a path with nothing at it.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import hvac.exceptions
import pytest

from diagnos.crypto.encoding import b64url_decode
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import SecretBox
from diagnos.errors import ConfigError
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.unseal import OpenBaoStore, UnsealedState
from diagnos.transport.config import Settings


class _FakeKvV2:
    """In-memory stand-in for OpenBao's KV v2 secrets engine."""

    def __init__(self) -> None:
        """One flat dict keyed by `(mount_point, path)`."""
        self._store: dict[tuple[str, str], dict[str, Any]] = {}

    def create_or_update_secret(self, *, path: str, secret: dict[str, Any], mount_point: str) -> None:
        """Overwrite whatever was at `path`."""
        self._store[(mount_point, path)] = secret

    def read_secret_version(
        self, *, path: str, mount_point: str, raise_on_deleted_version: bool = True
    ) -> dict[str, Any]:
        """`hvac`'s real shape (`{"data": {"data": ...}}`), or the real `InvalidPath`."""
        key = (mount_point, path)
        if key not in self._store:
            raise hvac.exceptions.InvalidPath()
        return {"data": {"data": self._store[key]}}

    def delete_metadata_and_all_versions(self, *, path: str, mount_point: str) -> None:
        """Forget whatever was at `path`, if anything."""
        self._store.pop((mount_point, path), None)


def _fake_hvac_client() -> Any:
    """An object shaped like `hvac.Client(...).secrets.kv.v2`."""
    return _fake_hvac_client_and_kv()[0]


def _fake_hvac_client_and_kv() -> tuple[Any, _FakeKvV2]:
    """Same as `_fake_hvac_client`, plus a direct handle to the in-memory `_FakeKvV2` behind it.

    The direct handle is what lets a test inspect exactly what `save()` wrote
    — raw, pre-`hvac`-envelope — without reaching through `restore()`'s own
    parsing.
    """
    kv_v2 = _FakeKvV2()
    kv = types.SimpleNamespace(v2=kv_v2)
    secrets_ns = types.SimpleNamespace(kv=kv)
    return types.SimpleNamespace(secrets=secrets_ns), kv_v2


def _settings() -> Settings:
    """Settings with the OpenBao defaults; only `api_token` is required."""
    return Settings(api_token="apikey-test")  # noqa: S106 — fixture, not a real secret


def _keyring(*, expires_at: int) -> Keyring:
    """A `Keyring` with one recognizable group DEK, for round-trip comparison.

    Each key is its own `SecretBox` — not a shared `bytearray` literal — so
    the same fixture can be `save()`d more than once across a test without
    an earlier reveal-and-zero silently emptying it for a later assertion.
    """
    session = SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(b"\x01" * 32)),
        enc_key=SecretBox.from_bytes(bytearray(b"\x02" * 32)),
        expires_at=expires_at,
    )
    return Keyring(
        enrollment_id="enr_1", session=session, group_keys={"sg1": SecretBox.from_bytes(bytearray(b"\x03" * 32))}
    )


def test_save_then_restore_reproduces_keypair_and_keyring() -> None:
    """A saved state restores with the same public keys and the same keyring contents."""
    store = OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1", client=_fake_hvac_client())
    keypair = HybridKeyPair.generate()
    keyring = _keyring(expires_at=10_000)
    store.save(UnsealedState(keypair=keypair, keyring=keyring))

    restored = store.restore(now=9_000)  # 1000 s left, well over the 60 s margin

    assert restored is not None
    assert restored.keypair.x25519_public == keypair.x25519_public
    assert restored.keypair.mlkem768_public == keypair.mlkem768_public
    assert restored.keyring.enrollment_id == keyring.enrollment_id
    assert restored.keyring.session.session_id == keyring.session.session_id
    assert isinstance(restored.keyring.session.sign_key, SecretBox)
    assert isinstance(restored.keyring.session.enc_key, SecretBox)
    assert restored.keyring.session.sign_key.reveal() == keyring.session.sign_key.reveal()
    assert restored.keyring.session.enc_key.reveal() == keyring.session.enc_key.reveal()
    assert restored.keyring.session.expires_at == keyring.session.expires_at
    assert restored.keyring.group_key("sg1") == keyring.group_key("sg1")


def test_restore_returns_none_once_inside_the_expiry_margin() -> None:
    """Fewer than 60 s left before `session_expires_at` counts as unusable."""
    store = OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1", client=_fake_hvac_client())
    keypair = HybridKeyPair.generate()
    store.save(UnsealedState(keypair=keypair, keyring=_keyring(expires_at=10_000)))

    assert store.restore(now=9_941) is None  # 59 s left
    assert store.restore(now=10_000) is None  # already at expiry


def test_restore_returns_none_when_nothing_was_saved() -> None:
    """An empty store restores to `None`, not an exception."""
    store = OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1", client=_fake_hvac_client())
    assert store.restore(now=0) is None


def test_clear_then_restore_returns_none() -> None:
    """`clear()` removes the saved state; `restore()` afterwards sees nothing."""
    store = OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1", client=_fake_hvac_client())
    keypair = HybridKeyPair.generate()
    store.save(UnsealedState(keypair=keypair, keyring=_keyring(expires_at=10_000)))
    assert store.restore(now=0) is not None

    store.clear()

    assert store.restore(now=0) is None


def test_missing_hvac_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the optional `hvac` dependency installed, construction raises `ConfigError`."""
    monkeypatch.setitem(sys.modules, "hvac", None)

    with pytest.raises(ConfigError):
        OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1")


def test_save_writes_b64url_that_decodes_to_the_original_bytes_and_leaves_the_keyring_usable() -> None:
    """`save()` writes plain b64url strings decoding to the exact key bytes, and never wipes the live keyring.

    `_Exporter` reveals each box into a throwaway `bytearray` and zeroes
    *that* buffer once the request body is built (`session/unseal.py`); the
    box itself — the one the caller keeps using after `save()` returns — is
    never touched. This test checks both halves of that promise directly
    against the fake KV's raw storage, not through `restore()`'s own parsing.
    """
    client, kv = _fake_hvac_client_and_kv()
    store = OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1", client=client)
    keypair = HybridKeyPair.generate()
    keyring = _keyring(expires_at=10_000)
    expected_sign_key = bytes(keyring.session.sign_key.reveal())
    expected_group_dek = bytes(keyring.group_key("sg1").reveal())

    store.save(UnsealedState(keypair=keypair, keyring=keyring))

    raw = kv._store[("secret", "diagnos/ws_1/acc_1")]  # noqa: SLF001 — test reaches into the fake's raw storage on purpose
    assert isinstance(raw["sign_key"], str)
    assert b64url_decode(raw["sign_key"]) == expected_sign_key
    assert b64url_decode(raw["group_keys"]["sg1"]) == expected_group_dek

    # the live keyring's own boxes still work after `save()` returned.
    assert keyring.session.sign_key.reveal() == bytearray(expected_sign_key)
    assert keyring.group_key("sg1").reveal() == bytearray(expected_group_dek)


def test_restore_returns_none_for_an_unrecognized_state_version() -> None:
    """A saved `"v"` this SDK does not recognize is treated exactly like "nothing saved"."""
    client, kv = _fake_hvac_client_and_kv()
    store = OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1", client=client)
    store.save(UnsealedState(keypair=HybridKeyPair.generate(), keyring=_keyring(expires_at=10_000)))
    raw = kv._store[("secret", "diagnos/ws_1/acc_1")]  # noqa: SLF001 — mutating the fake's raw storage on purpose
    raw["v"] = 999

    assert store.restore(now=0) is None


def test_construction_without_a_client_builds_a_real_hvac_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an injected `client`, `OpenBaoStore` builds a real `hvac.Client` from `settings`.

    `hvac.Client` itself is replaced with a recording double so this proves
    only `OpenBaoStore`'s own wiring (`url`/`token`/`namespace` from
    `settings`) — never opening a real socket to an OpenBao server.
    """
    calls: list[dict[str, Any]] = []

    class _DummyHvacClient:
        def __init__(self, *, url: str | None, token: str | None, namespace: str | None) -> None:
            calls.append({"url": url, "token": token, "namespace": namespace})

    monkeypatch.setattr("hvac.Client", _DummyHvacClient)

    settings = Settings(
        api_token="apikey-test",  # noqa: S106 — fixture, not a real secret
        openbao_addr="https://bao.example.test",
        openbao_token="s.supersecrettoken",  # noqa: S106 — fixture, not a real secret
        openbao_namespace="team-a",
    )

    store = OpenBaoStore(settings, workspace_id="ws_1", account_id="acc_1")

    assert isinstance(store._client, _DummyHvacClient)  # noqa: SLF001 — the wiring itself is what's under test
    assert calls == [{"url": "https://bao.example.test", "token": "s.supersecrettoken", "namespace": "team-a"}]


def test_restore_returns_secret_boxes_for_every_key() -> None:
    """`restore()` never hands back raw `bytes`/`bytearray` — every key comes back as a `SecretBox`."""
    store = OpenBaoStore(_settings(), workspace_id="ws_1", account_id="acc_1", client=_fake_hvac_client())
    store.save(UnsealedState(keypair=HybridKeyPair.generate(), keyring=_keyring(expires_at=10_000)))

    restored = store.restore(now=9_000)

    assert restored is not None
    assert isinstance(restored.keyring.session.sign_key, SecretBox)
    assert isinstance(restored.keyring.session.enc_key, SecretBox)
    assert isinstance(restored.keyring.group_key("sg1"), SecretBox)
