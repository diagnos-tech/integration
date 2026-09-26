"""🇺🇸 `Diagnos`: settings resolution, identity properties, lazy unlock, and lock/close/context manager.

`transport`/`session` are the escape hatches `client.py`'s own docstring
names — a `_FakeSession` stands in for `SessionManager` (recording
`unlock()`/`lock()` the way `session/test_manager.py` fakes `enroll()`), so
these tests exercise `Diagnos` itself: what it reads straight off the
token, what it defers until a keyring is actually needed, and what
`lock()`/`close()`/the context manager each do and do not touch. What
`Diagnos` builds when a caller does *not* pass `transport`/`session` at all
lives in `test_client_wiring.py`, a separate file per this package's own
~400-line convention.

🇧🇷 `Diagnos`: resolução de settings, propriedades de identidade, unlock
preguiçoso, e lock/close/gerenciador de contexto.

`transport`/`session` são as válvulas de escape que a própria docstring de
`client.py` nomeia — um `_FakeSession` substitui `SessionManager`
(registrando `unlock()`/`lock()` do jeito que `session/test_manager.py`
substitui `enroll()`), então estes testes exercitam o próprio `Diagnos`: o
que ele lê direto do token, o que ele adia até um keyring ser de fato
necessário, e o que `lock()`/`close()`/o gerenciador de contexto tocam ou
não. O que `Diagnos` constrói quando quem chama *não* passa
`transport`/`session` mora em `test_client_wiring.py`, um arquivo separado
seguindo a própria convenção do pacote de ~400 linhas.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import pytest
from diagnos.client import Diagnos, _print_enrollment_prompt_fallback, _resolve_settings
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.errors import SessionExpiredError
from diagnos.models import ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.resources.drives import Drives
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.manager import default_prompt
from diagnos.transport.config import Settings

_VALID_PAYLOAD = {
    "sub": "key_123",
    "account_id": "acc_1",
    "workspace_id": "ws_1",
    "name": "svc@ws_1.diagnos.health",
}


def _make_apikey(payload: dict[str, object] | None = None) -> str:
    """🇺🇸 A syntactically valid `apikey-<jwt>`, unsigned — `ServiceAccountToken.parse` never checks it.

    🇧🇷 Um `apikey-<jwt>` sintaticamente válido, sem assinatura — `ServiceAccountToken.parse` nunca a confere.
    """
    payload = payload if payload is not None else _VALID_PAYLOAD
    header_b64 = b64url_encode(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))
    signature_b64 = b64url_encode(b"fake-signature")
    return f"apikey-{header_b64}.{payload_b64}.{signature_b64}"


def _settings(**overrides: Any) -> Settings:
    """🇺🇸 `Settings` with a valid token for `ws_1`/`acc_1`, everything else overridable.

    🇧🇷 `Settings` com um token válido para `ws_1`/`acc_1`, o resto sobrescrevível.
    """
    return Settings(api_token=_make_apikey(), **overrides)


class _FakeTransport:
    """🇺🇸 Records whether `close()` ran; nothing here ever needs to send a request.

    🇧🇷 Registra se `close()` rodou; nada aqui precisa mandar uma requisição.
    """

    def __init__(self) -> None:
        """🇺🇸 Starts open. 🇧🇷 Começa aberto."""
        self.closed = False

    def close(self) -> None:
        """🇺🇸 Marks itself closed. 🇧🇷 Marca-se como fechado."""
        self.closed = True


def _fresh_keyring(*, group_ids: tuple[str, ...] = ("sg1",)) -> Keyring:
    """🇺🇸 A `Keyring` valid far into the future, holding one DEK per `group_ids`.

    🇧🇷 Um `Keyring` válido bem no futuro, com uma DEK por `group_ids`.
    """
    session = SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(b"\x01" * 32)),
        enc_key=SecretBox.from_bytes(bytearray(b"\x02" * 32)),
        expires_at=9_999_999_999,
    )
    return Keyring(
        enrollment_id="enr_1",
        session=session,
        group_keys={group_id: SecretBox.from_bytes(bytearray(b"\x03" * 32)) for group_id in group_ids},
    )


@dataclass
class _FakeSession:
    """🇺🇸 A `SessionManager` stand-in: mirrors its `keyring`/`unlock`/`lock`/`session_keys` shape exactly.

    🇧🇷 Um substituto de `SessionManager`: espelha exatamente a forma de `keyring`/`unlock`/`lock`/`session_keys`.
    """

    _keyring: Keyring | None = field(default=None)
    unlock_calls: int = 0
    lock_calls: int = 0

    @property
    def keyring(self) -> Keyring:
        """🇺🇸 Same contract as `SessionManager.keyring`: raises without a live session.

        🇧🇷 Mesmo contrato de `SessionManager.keyring`: lança sem sessão viva.
        """
        if self._keyring is None:
            raise SessionExpiredError("no live session")
        return self._keyring

    def unlock(self) -> Keyring:
        """🇺🇸 Counts the call; builds a fresh keyring only the first time. 🇧🇷 Conta a chamada; só cria na 1ª vez."""
        self.unlock_calls += 1
        if self._keyring is None:
            self._keyring = _fresh_keyring()
        return self._keyring

    def lock(self) -> None:
        """🇺🇸 Counts the call and drops the keyring. 🇧🇷 Conta a chamada e descarta o keyring."""
        self.lock_calls += 1
        self._keyring = None

    def session_keys(self) -> SessionKeys | None:
        """🇺🇸 The mirror of `SessionManager.session_keys`: `None`, never a raise. 🇧🇷 O espelho de `session_keys`."""
        return self._keyring.session if self._keyring is not None else None


# -- _resolve_settings ---------------------------------------------------------


def test_resolve_settings_prefers_explicit_settings_over_token() -> None:
    """🇺🇸 An explicit `settings` wins outright, even with a `token` also given.

    🇧🇷 Um `settings` explícito vence direto, mesmo com um `token` também dado.
    """
    settings = _settings()
    assert _resolve_settings(settings, "apikey-ignored-token") is settings


def test_resolve_settings_token_overrides_env_token_but_keeps_other_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `token` replaces only `DIAGNOS_API_TOKEN`; every other env var still comes from the real environment.

    🇧🇷 `token` substitui só `DIAGNOS_API_TOKEN`; toda outra env var ainda vem do ambiente real.
    """
    monkeypatch.setattr(
        os, "environ", {"DIAGNOS_API_TOKEN": "apikey-old", "DIAGNOS_VAULT_URL": "https://custom.example.test"}
    )
    settings = _resolve_settings(None, "apikey-new")
    assert settings.api_token == "apikey-new"  # noqa: S105 — fixture, not a real secret
    assert settings.vault_url == "https://custom.example.test"


def test_resolve_settings_falls_back_to_the_environment_when_neither_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 Neither `settings` nor `token`: reads `Settings.from_env()` straight from `os.environ`.

    🇧🇷 Nem `settings` nem `token`: lê `Settings.from_env()` direto de `os.environ`.
    """
    monkeypatch.setattr(os, "environ", {"DIAGNOS_API_TOKEN": "apikey-from-env"})
    settings = _resolve_settings(None, None)
    assert settings.api_token == "apikey-from-env"  # noqa: S105 — fixture, not a real secret


def test_print_enrollment_prompt_fallback_returns_the_manager_default() -> None:
    """🇺🇸 The deferred-import wrapper returns exactly `session.manager.default_prompt`.

    🇧🇷 O wrapper de import adiado devolve exatamente `session.manager.default_prompt`.
    """
    assert _print_enrollment_prompt_fallback() is default_prompt


# -- identity properties -------------------------------------------------------


def test_identity_properties_read_from_the_token_without_unlocking() -> None:
    """🇺🇸 `workspace_id`/`account_id`/`name`/`key_id` never touch the session.

    🇧🇷 `workspace_id`/`account_id`/`name`/`key_id` nunca tocam a sessão.
    """
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), session=_FakeSession())
    assert vault.workspace_id == "ws_1"
    assert vault.account_id == "acc_1"
    assert vault.name == "svc@ws_1.diagnos.health"
    assert vault.key_id == "key_123"


def test_security_groups_is_empty_before_unlock_and_populated_after() -> None:
    """🇺🇸 `[]` while the session has no live keyring; the group ids once it does.

    🇧🇷 `[]` enquanto a sessão não tem keyring vivo; os ids de grupo assim que tem.
    """
    session = _FakeSession()
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), session=session)
    assert vault.security_groups == []

    session.unlock()

    assert vault.security_groups == ["sg1"]


def test_repr_never_leaks_the_raw_token_but_shows_the_identity() -> None:
    """🇺🇸 `repr(vault)` carries `workspace_id`/`account_id`/`name`, never the raw `apikey-<jwt>`.

    🇧🇷 `repr(vault)` carrega `workspace_id`/`account_id`/`name`, nunca o `apikey-<jwt>` cru.
    """
    raw = _make_apikey()
    vault = Diagnos(settings=Settings(api_token=raw), transport=_FakeTransport(), session=_FakeSession())

    rendered = repr(vault)

    assert raw not in rendered
    assert "ws_1" in rendered
    assert "acc_1" in rendered
    assert "apikey-…" in rendered


# -- lazy keyring access -------------------------------------------------------


def test_keyring_provider_falls_back_to_unlock_when_no_live_session() -> None:
    """🇺🇸 The private keyring provider unlocks the session on first use, exactly once.

    🇧🇷 O provedor privado de keyring desbloqueia a sessão no primeiro uso, exatamente uma vez.
    """
    session = _FakeSession()
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), session=session)

    keyring = vault._keyring_provider()  # noqa: SLF001 — the lazy-unlock path under test

    assert session.unlock_calls == 1
    assert keyring is session.keyring


def test_keyring_provider_reuses_a_live_keyring_without_unlocking_again() -> None:
    """🇺🇸 An already-unlocked session is reused; `unlock()` is not called a second time.

    🇧🇷 Uma sessão já desbloqueada é reaproveitada; `unlock()` não é chamado de novo.
    """
    session = _FakeSession()
    session.unlock()
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), session=session)

    keyring = vault._keyring_provider()  # noqa: SLF001

    assert session.unlock_calls == 1
    assert keyring is session.keyring


# -- lazily built resources -----------------------------------------------------


def test_patients_exams_drives_are_built_once_and_cached() -> None:
    """🇺🇸 Each of `patients`/`exams`/`drives` is the exact same object on every access.

    🇧🇷 Cada um de `patients`/`exams`/`drives` é o mesmo objeto exato em todo acesso.
    """
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), session=_FakeSession())

    assert isinstance(vault.patients, Patients)
    assert vault.patients is vault.patients
    assert isinstance(vault.exams, Exams)
    assert vault.exams is vault.exams
    assert isinstance(vault.drives, Drives)
    assert vault.drives is vault.drives


def test_patients_and_exams_wire_the_right_resource_models_and_time_precision() -> None:
    """🇺🇸 `patients`/`exams` carry their own resource name, record/summary models, and the settings' precision.

    🇧🇷 `patients`/`exams` carregam o próprio nome de recurso, modelos de registro/resumo, e a precisão de settings.
    """
    vault = Diagnos(settings=_settings(time_precision="day"), transport=_FakeTransport(), session=_FakeSession())

    patients_engine = vault.patients._documents  # noqa: SLF001 — asserting the private wiring itself
    assert patients_engine._resource == "patients"  # noqa: SLF001
    assert patients_engine._record_model is PatientRecord  # noqa: SLF001
    assert patients_engine._summary_model is PatientSummary  # noqa: SLF001
    assert vault.patients._time_precision == "day"  # noqa: SLF001

    exams_engine = vault.exams._documents  # noqa: SLF001
    assert exams_engine._resource == "exams"  # noqa: SLF001
    assert exams_engine._record_model is ExamRecord  # noqa: SLF001
    assert exams_engine._summary_model is ExamSummary  # noqa: SLF001
    assert vault.exams._time_precision == "day"  # noqa: SLF001


def test_drives_is_wired_to_the_same_workspace() -> None:
    """🇺🇸 `vault.drives` targets the workspace's own `/nodes` base path.

    🇧🇷 `vault.drives` mira o próprio path base `/nodes` do workspace.
    """
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), session=_FakeSession())
    assert vault.drives._nodes._base == "/api/external/v1/workspaces/ws_1/nodes"  # noqa: SLF001


# -- unlock / lock / close / context manager -----------------------------------


def test_unlock_and_lock_delegate_to_the_session() -> None:
    """🇺🇸 `vault.unlock()`/`vault.lock()` are thin delegations to the session.

    🇧🇷 `vault.unlock()`/`vault.lock()` são delegações diretas à sessão.
    """
    session = _FakeSession()
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), session=session)

    keyring = vault.unlock()
    assert session.unlock_calls == 1
    assert keyring is session.keyring

    vault.lock()
    assert session.lock_calls == 1


def test_close_closes_the_transport_and_never_locks() -> None:
    """🇺🇸 `close()` closes the transport; it must not end the session.

    🇧🇷 `close()` fecha o transporte; não pode encerrar a sessão.
    """
    transport = _FakeTransport()
    session = _FakeSession()
    vault = Diagnos(settings=_settings(), transport=transport, session=session)

    vault.close()

    assert transport.closed is True
    assert session.lock_calls == 0


def test_context_manager_unlocks_on_enter_and_closes_without_locking_on_exit() -> None:
    """🇺🇸 `with Diagnos(...)` unlocks on entry and closes — but does not lock — on exit.

    🇧🇷 `with Diagnos(...)` desbloqueia na entrada e fecha — mas não trava — na saída.
    """
    transport = _FakeTransport()
    session = _FakeSession()

    with Diagnos(settings=_settings(), transport=transport, session=session) as vault:
        assert session.unlock_calls == 1
        assert vault.security_groups == ["sg1"]

    assert transport.closed is True
    assert session.lock_calls == 0
