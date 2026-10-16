"""🇺🇸 `Diagnos` with the service account token: every way to pass it, what it exposes, `whoami`, the legacy path.

🇧🇷 `Diagnos` com o token de conta de serviço: toda forma de passá-lo, o que expõe, `whoami`, o caminho legado.
"""

from __future__ import annotations

import warnings
from typing import Any

import keyring
import pytest
from _stores import MemoryKeyring
from _tokens import legacy_token, mint

from diagnos import ConfigError, Diagnos, DiagnosToken, LegacyTokenWarning, Settings, Whoami
from diagnos.crypto.secure import SecretBox
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.token_store import SERVICE


class _Inert:
    """🇺🇸 Transport and session stand-in: these tests never reach the network. 🇧🇷 Estes testes nunca chegam à rede."""

    def __init__(self) -> None:
        """🇺🇸 A session that unlocks to one group. 🇧🇷 Uma sessão que desbloqueia um grupo."""
        session = SessionKeys("ses_1", SecretBox.random(32), SecretBox.random(32), 4_000_000_000)
        self.live = Keyring(enrollment_id="ses_1", session=session, group_keys={"sg_1": SecretBox.random(32)})
        self.reopened = 0

    def close(self) -> None:
        """🇺🇸 Nothing to close. 🇧🇷 Nada a fechar."""

    @property
    def keyring(self) -> Keyring:
        """🇺🇸 Always unlocked. 🇧🇷 Sempre desbloqueada."""
        return self.live

    def reopen(self) -> bool:
        """🇺🇸 Counts the transport's requests for a new session. 🇧🇷 Conta os pedidos de sessão nova."""
        self.reopened += 1
        return True


def client(**kwargs: Any) -> Diagnos:
    """🇺🇸 `Diagnos(**kwargs)` without network. 🇧🇷 `Diagnos(**kwargs)` sem rede."""
    inert = _Inert()
    return Diagnos(transport=inert, session=inert, **kwargs)  # type: ignore[arg-type]


def test_a_token_text_exposes_the_identity_and_never_the_seed_in_repr() -> None:
    """🇺🇸 `token="dgn_sk1_…"`: identity properties, no account id or name, `repr` with the identity only.

    🇧🇷 `token="dgn_sk1_…"`: propriedades de identidade, sem id de conta nem nome, `repr` só com a identidade.
    """
    text = mint("wsClient")
    vault = client(token=text)
    assert vault.identity is not None and vault.identity.endswith("@wsClient.diagnos.health")
    assert (vault.workspace_id, vault.key_id) == ("wsClient", vault.identity.partition("@")[0])
    assert (vault.account_id, vault.name, vault.email) == (None, None, None)
    assert (vault.token_kind, vault.token_source) == ("hybrid", "token= · --token")
    assert text[8:] not in repr(vault)
    assert repr(vault) == f"Diagnos(workspace_id='wsClient', identity='{vault.identity}')"


def test_explicit_settings_without_any_token_are_refused() -> None:
    """🇺🇸 `Settings()` alone names where a token comes from. 🇧🇷 `Settings()` sozinho diz de onde vem um token."""
    with pytest.raises(ConfigError, match="diagnos login"):
        client(settings=Settings())


def test_an_object_and_explicit_settings_work_and_the_token_overrides_settings() -> None:
    """🇺🇸 A `DiagnosToken` object; over explicit `Settings`, the token replaces only the identity.

    🇧🇷 Um objeto `DiagnosToken`; sobre `Settings` explícitos, o token substitui só a identidade.
    """
    token = DiagnosToken.parse(mint("wsObj"), source="mine")
    assert client(token=token).token_source == "mine"  # noqa: S105 — a source label
    settings = Settings(vault_url="https://vault.test", api_token=legacy_token())
    vault = client(settings=settings, token=mint("wsOver"))
    assert (vault.workspace_id, vault._settings.vault_url) == ("wsOver", "https://vault.test")  # noqa: SLF001
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LegacyTokenWarning)
        assert client(settings=settings, token=legacy_token("wsIgnored")).workspace_id == "wsLegacy"


def test_from_env_reads_the_environment_and_never_the_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `Diagnos.from_env` is for CI and servers; `Diagnos()` also reads the keyring `diagnos login` filled.

    🇧🇷 `Diagnos.from_env` é para CI e servidores; `Diagnos()` também lê o chaveiro que o `diagnos login` encheu.
    """
    backend = MemoryKeyring()
    backend.items[(SERVICE, "https://vault.diagnos.health")] = mint("wsStored")
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    monkeypatch.delenv("DIAGNOS_TOKEN", raising=False)
    monkeypatch.delenv("DIAGNOS_API_TOKEN", raising=False)
    monkeypatch.delenv("OPENBAO_ADDR", raising=False)
    inert = _Inert()
    from_keyring = Diagnos(transport=inert, session=inert)  # type: ignore[arg-type]
    assert from_keyring.token_source == "keyring"  # noqa: S105 — a source label
    with pytest.raises(ConfigError, match="No diagnos token found"):
        Diagnos.from_env()
    monkeypatch.setenv("DIAGNOS_TOKEN", mint("wsEnv"))
    assert Diagnos.from_env(transport=inert, session=inert).workspace_id == "wsEnv"
    assert Diagnos.from_env({"DIAGNOS_TOKEN": mint("wsMap")}, transport=inert, session=inert).workspace_id == "wsMap"


def test_whoami_proves_the_token_with_a_session_and_reports_it() -> None:
    """🇺🇸 Identity, source, the session's groups and expiry — all public, nothing secret.

    🇧🇷 Identidade, origem, os grupos e a validade da sessão — tudo público, nada secreto.
    """
    vault = client(token=mint("wsWho"))
    who = vault.whoami()
    assert isinstance(who, Whoami)
    assert (who.identity, who.key_id, who.workspace_id) == (vault.identity, vault.key_id, "wsWho")
    assert (who.token_kind, who.token_source, who.security_groups, who.session_expires_at) == (
        "hybrid",
        "token= · --token",
        ["sg_1"],
        4_000_000_000,
    )


def test_the_transport_asks_the_session_owner_for_a_new_session() -> None:
    """🇺🇸 `on_session_lost` is wired to `SessionManager.reopen`. 🇧🇷 O `on_session_lost` vai ao `reopen`."""
    inert = _Inert()
    vault = Diagnos(token=mint(), session=inert)  # type: ignore[arg-type]
    assert vault._transport._reopen_session() is True  # noqa: SLF001
    assert inert.reopened == 1


def test_the_legacy_token_still_works_and_warns_at_the_callers_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `token="apikey-…"` keeps working and warns *here*, naming `diagnos login` and `DIAGNOS_TOKEN`.

    🇧🇷 `token="apikey-…"` continua funcionando e avisa *aqui*, citando `diagnos login` e `DIAGNOS_TOKEN`.
    """
    monkeypatch.setenv("DIAGNOS_TOKEN", mint())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        vault = client(token=legacy_token())
    legacy = [warning for warning in caught if issubclass(warning.category, LegacyTokenWarning)]
    assert len(legacy) == 1 and legacy[0].filename == __file__
    message = str(legacy[0].message)
    assert "2027-04-15" in message and "diagnos login" in message and "DIAGNOS_TOKEN" in message
    assert (vault.token_kind, vault.identity, vault.account_id, vault.token_source) == (
        "legacy_apikey",
        None,
        "acc_9",
        "DIAGNOS_API_TOKEN",
    )
    assert (vault.workspace_id, vault.key_id, vault.name) == ("wsLegacy", "key_9", "bot")
    assert "api_token='apikey-…" in repr(vault)
