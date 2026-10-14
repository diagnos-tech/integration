"""`SessionManager`: restore-or-enroll on `unlock()`, and full teardown on `lock()`.

`unlock()`/`lock()` are exercised against fakes for `enroll()`'s two
dependencies (`VaultTransport`, `OpenBaoStore`) rather than a real
`httpx.MockTransport` — the enrollment *protocol* itself is already covered
byte-for-byte in `test_enrollment.py`; what matters here is only the
orchestration: does a valid restore skip enrollment, does a missing one
trigger it, does `lock()` clear everything regardless of what the network
does.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Any

import pytest

from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import SecretBox
from diagnos.errors import SessionExpiredError
from diagnos.session.enrollment import EnrollmentPrompt
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.manager import SessionManager
from diagnos.session.unseal import UnsealedState


@dataclass
class _FakeTransport:
    """Records every `post()` call; `enroll()` itself is monkeypatched away in these tests."""

    posts: list[tuple[str, bool]]

    def post(self, path: str, *, json: Any | None = None, signed: bool = True) -> None:
        """Only `lock()` calls this in these tests; no real HTTP involved."""
        self.posts.append((path, signed))


class _FakeStore:
    """An `OpenBaoStore` stand-in: an in-memory slot instead of OpenBao."""

    def __init__(self, initial: UnsealedState | None = None) -> None:
        """Starts pre-loaded (or not) so tests control the restore outcome directly."""
        self._state = initial
        self.save_calls: list[UnsealedState] = []
        self.clear_calls = 0

    def restore(self, *, now: int | None = None) -> UnsealedState | None:
        """Whatever was pre-loaded (or saved), regardless of `now`."""
        return self._state

    def save(self, state: UnsealedState) -> None:
        """Records the call and remembers the state, so a later `restore()` would see it."""
        self.save_calls.append(state)
        self._state = state

    def clear(self) -> None:
        """Counts calls and drops whatever was stored."""
        self.clear_calls += 1
        self._state = None


def _fake_settings() -> Any:
    """The one field `SessionManager.unlock()` reads off `settings` directly: `harden_process`.

    `harden_process=False` skips the real `harden_process()` call (`crypto/secure.py`)
    so these orchestration-only tests never depend on the host's actual
    hardening support — a bare `object()` no longer works here since
    `unlock()` now reads `settings.harden_process` on every call.
    """
    return types.SimpleNamespace(harden_process=False)


def _keyring(*, expires_at: int = 9_999_999_999) -> Keyring:
    """A `Keyring` with recognizable, fixed bytes, each key its own `SecretBox`."""
    session = SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(b"\x01" * 32)),
        enc_key=SecretBox.from_bytes(bytearray(b"\x02" * 32)),
        expires_at=expires_at,
    )
    return Keyring(
        enrollment_id="enr_1", session=session, group_keys={"sg1": SecretBox.from_bytes(bytearray(b"\x03" * 32))}
    )


def test_unlock_with_a_valid_restore_skips_enrollment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A store holding a still-valid session means `unlock()` never calls `enroll()`."""

    def _must_not_enroll(*args: Any, **kwargs: Any) -> Keyring:
        raise AssertionError("enroll() must not be called when the store has a valid session")

    monkeypatch.setattr("diagnos.session.manager.enroll", _must_not_enroll)

    keypair = HybridKeyPair.generate()
    keyring = _keyring(expires_at=9_999_999_999)
    store = _FakeStore(initial=UnsealedState(keypair=keypair, keyring=keyring))

    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        store=store,  # type: ignore[arg-type]
        now=lambda: 0.0,
    )

    result = manager.unlock()

    assert result is manager.keyring
    assert result.enrollment_id == "enr_1"
    assert manager.keypair is keypair
    assert store.save_calls == []  # nothing new to save — it came from the store already


def test_unlock_without_a_store_enrolls_and_has_nothing_to_save(monkeypatch: pytest.MonkeyPatch) -> None:
    """No `store` at all: `unlock()` enrolls fresh every time, no save attempted."""
    keyring = _keyring()
    calls: list[Any] = []

    def _fake_enroll(transport: Any, token: Any, keypair: Any, *, on_prompt: Any, sleep: Any, now: Any) -> Keyring:
        calls.append((transport, token, keypair))
        on_prompt(EnrollmentPrompt(enrollment_id="enr_1", approval_url="https://x", code="000000", expires_at=1))
        return keyring

    monkeypatch.setattr("diagnos.session.manager.enroll", _fake_enroll)

    prompts: list[EnrollmentPrompt] = []
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=prompts.append,
        now=lambda: 0.0,
    )

    result = manager.unlock()

    assert result is keyring
    assert len(calls) == 1
    assert len(prompts) == 1


def test_unlock_without_a_restore_enrolls_and_saves_to_the_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty store: `unlock()` enrolls and then saves the fresh state."""
    keyring = _keyring()
    fresh_keypair = HybridKeyPair.generate()

    def _fake_enroll(transport: Any, token: Any, keypair: Any, *, on_prompt: Any, sleep: Any, now: Any) -> Keyring:
        return keyring

    monkeypatch.setattr("diagnos.session.manager.enroll", _fake_enroll)
    monkeypatch.setattr(HybridKeyPair, "generate", staticmethod(lambda: fresh_keypair))

    store = _FakeStore(initial=None)
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        store=store,  # type: ignore[arg-type]
        now=lambda: 0.0,
    )

    result = manager.unlock()

    assert result is keyring
    assert len(store.save_calls) == 1
    assert store.save_calls[0].keyring is keyring
    assert store.save_calls[0].keypair is fresh_keypair


def test_lock_posts_clears_store_and_zeroizes_keys() -> None:
    """`lock()` calls `session/lock`, clears the store, and wipes every key."""
    keypair = HybridKeyPair.generate()
    keyring = _keyring()
    store = _FakeStore(initial=UnsealedState(keypair=keypair, keyring=keyring))
    transport = _FakeTransport(posts=[])

    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=transport,  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        store=store,  # type: ignore[arg-type]
        now=lambda: 0.0,
    )
    manager.unlock()

    manager.lock()

    assert transport.posts == [("/api/external/v1/session/lock", True)]
    assert store.clear_calls == 1
    assert keyring.session.sign_key.is_wiped is True
    assert keyring.session.enc_key.is_wiped is True
    assert keyring.group_keys["sg1"].is_wiped is True
    assert keypair.is_wiped is True


def test_lock_ignores_transport_errors() -> None:
    """A `post()` that raises still results in a fully cleared, locked manager."""

    class _ExplodingTransport:
        def post(self, path: str, *, json: Any | None = None, signed: bool = True) -> None:
            raise ConnectionError("network is down")

    store = _FakeStore(initial=UnsealedState(keypair=HybridKeyPair.generate(), keyring=_keyring()))
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_ExplodingTransport(),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        store=store,  # type: ignore[arg-type]
        now=lambda: 0.0,
    )
    manager.unlock()

    manager.lock()  # must not raise

    assert store.clear_calls == 1
    assert manager.keypair is None


def test_keyring_property_raises_session_expired_after_lock() -> None:
    """After `lock()`, the `keyring` property raises `SessionExpiredError`."""
    store = _FakeStore(initial=UnsealedState(keypair=HybridKeyPair.generate(), keyring=_keyring()))
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        store=store,  # type: ignore[arg-type]
        now=lambda: 0.0,
    )
    manager.unlock()

    manager.lock()

    with pytest.raises(SessionExpiredError):
        _ = manager.keyring
    assert manager.session_keys() is None


def test_keyring_property_raises_session_expired_before_any_unlock() -> None:
    """Before `unlock()` is ever called, the `keyring` property already raises."""
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        now=lambda: 0.0,
    )
    with pytest.raises(SessionExpiredError):
        _ = manager.keyring


def test_session_keys_returns_none_once_the_live_session_has_expired() -> None:
    """A keyring that is still set but past its margin makes `session_keys()` return `None`, not raise.

    This is the mirror-image path the `keyring` property does not have: a
    live `_keyring` whose *session* has lapsed. `session_keys()` is the
    provider `VaultTransport` polls on every signed request, so it must
    degrade to "nothing usable" quietly (`session/manager.py`).
    """
    now_box = {"t": 0.0}
    store = _FakeStore(initial=UnsealedState(keypair=HybridKeyPair.generate(), keyring=_keyring(expires_at=1_000)))
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        store=store,  # type: ignore[arg-type]
        now=lambda: now_box["t"],
    )
    manager.unlock()
    assert manager.session_keys() is not None  # well before expiry

    now_box["t"] = 999.0  # inside the 60 s margin

    assert manager.session_keys() is None
    with pytest.raises(SessionExpiredError):
        _ = manager.keyring


def test_harden_once_runs_harden_process_exactly_once_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `settings.harden_process=True`, `harden_process()` runs on the first `unlock()`, never again.

    `harden_process()` itself is monkeypatched away — this test is about
    `SessionManager`'s own idempotence (`_hardened`), not the OS-level
    effects `crypto/secure.py` already covers.
    """
    calls = {"n": 0}

    def _fake_harden_process() -> dict[str, object]:
        calls["n"] += 1
        return {"ok": True}

    monkeypatch.setattr("diagnos.session.manager.harden_process", _fake_harden_process)

    keyring = _keyring()

    def _fake_enroll(transport: Any, token: Any, keypair: Any, *, on_prompt: Any, sleep: Any, now: Any) -> Keyring:
        return keyring

    monkeypatch.setattr("diagnos.session.manager.enroll", _fake_enroll)

    manager = SessionManager(
        settings=types.SimpleNamespace(harden_process=True),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        now=lambda: 0.0,
    )

    manager.unlock()
    manager.lock()
    manager.unlock()  # a second unlock, after a lock in between

    assert calls["n"] == 1


def test_lock_before_any_unlock_still_posts_and_clears_the_store_harmlessly() -> None:
    """`lock()` with nothing ever unlocked still calls `session/lock` and clears the store, touching no keys."""
    store = _FakeStore(initial=None)
    transport = _FakeTransport(posts=[])
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=transport,  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        store=store,  # type: ignore[arg-type]
        now=lambda: 0.0,
    )

    manager.lock()  # must not raise

    assert transport.posts == [("/api/external/v1/session/lock", True)]
    assert store.clear_calls == 1
    assert manager.keypair is None


def test_lock_with_no_store_at_all_still_zeroizes_the_live_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """`lock()` with no `store` configured still wipes the keyring and key pair."""
    keyring = _keyring()

    def _fake_enroll(transport: Any, token: Any, keypair: Any, *, on_prompt: Any, sleep: Any, now: Any) -> Keyring:
        return keyring

    monkeypatch.setattr("diagnos.session.manager.enroll", _fake_enroll)
    manager = SessionManager(
        settings=_fake_settings(),
        token=object(),  # type: ignore[arg-type]
        transport=_FakeTransport(posts=[]),  # type: ignore[arg-type]
        on_prompt=lambda prompt: None,
        now=lambda: 0.0,
    )
    manager.unlock()
    keypair = manager.keypair
    assert keypair is not None

    manager.lock()

    assert keyring.session.sign_key.is_wiped is True
    assert keypair.is_wiped is True
    assert manager.keypair is None
