"""🇺🇸 Where `Settings.from_env` finds the token: environment first, then the keyring, then OpenBao.

Each test builds the exact situation — a variable, a stored token, both —
and checks which one wins, so a change of precedence fails here by name.

🇧🇷 Onde o `Settings.from_env` acha o token: ambiente primeiro, depois o chaveiro, depois o OpenBao.

Cada teste monta a situação exata — uma variável, um token guardado, os dois
— e confere qual vence, para uma mudança de precedência falhar aqui pelo
nome.
"""

from __future__ import annotations

from typing import Any

import hvac  # type: ignore[import-untyped]
import keyring
import pytest
from _stores import FakeOpenBao, InsecureKeyring, MemoryKeyring
from _tokens import legacy_token, mint

from diagnos import ConfigError, Settings, TokenError
from diagnos.token_store import SERVICE, Keychain
from diagnos.transport.service_token import DiagnosToken
from diagnos.transport.token_sources import FoundIdentity, find_identity

VAULT = "https://vault.diagnos.health"


@pytest.fixture
def secure_keyring(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyring:
    """🇺🇸 The process keyring is a secure, empty, in-memory one. 🇧🇷 Um chaveiro seguro, vazio, em memória."""
    backend = MemoryKeyring()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    return backend


@pytest.fixture
def bao(monkeypatch: pytest.MonkeyPatch) -> FakeOpenBao:
    """🇺🇸 Every `hvac.Client` built by the token store is this one. 🇧🇷 Todo `hvac.Client` do cofre de token é este."""
    fake = FakeOpenBao()
    monkeypatch.setattr(hvac, "Client", lambda **kwargs: fake)
    return fake


def _stored(bao: FakeOpenBao, text: str, prefix: str = "diagnos") -> None:
    """🇺🇸 What `diagnos login --store openbao` writes. 🇧🇷 O que o `diagnos login --store openbao` grava."""
    bao.data[("secret", f"{prefix}/token")] = {"v": 1, "token": text}


def test_the_environment_wins_over_every_store(secure_keyring: MemoryKeyring, bao: FakeOpenBao) -> None:
    """🇺🇸 `DIAGNOS_TOKEN` beats keyring and OpenBao; the legacy variable beats them too.

    🇧🇷 `DIAGNOS_TOKEN` vence chaveiro e OpenBao; a variável legada também vence os dois.
    """
    secure_keyring.items[(SERVICE, VAULT)] = mint("wsKeyring")
    _stored(bao, mint("wsBao"))
    env = {"DIAGNOS_TOKEN": mint("wsEnv"), "DIAGNOS_API_TOKEN": legacy_token(), "OPENBAO_ADDR": "https://bao"}
    settings = Settings.from_env(env, keyring=True)
    assert settings.token is not None and settings.token.workspace_id == "wsEnv"
    assert settings.token.source == "DIAGNOS_TOKEN"
    legacy = Settings.from_env({**env, "DIAGNOS_TOKEN": ""}, keyring=True)
    assert (legacy.token, legacy.api_token) == (None, env["DIAGNOS_API_TOKEN"])


def test_then_the_keyring_then_openbao(secure_keyring: MemoryKeyring, bao: FakeOpenBao) -> None:
    """🇺🇸 Nothing in the environment: the keyring entry for this vault URL, else OpenBao's `<prefix>/token`.

    🇧🇷 Nada no ambiente: a entrada do chaveiro desta URL de cofre, senão o `<prefixo>/token` do OpenBao.
    """
    _stored(bao, mint("wsBao"), prefix="team-a")
    env = {"OPENBAO_ADDR": "https://bao", "OPENBAO_PATH_PREFIX": "team-a"}
    secure_keyring.items[(SERVICE, VAULT)] = mint("wsKeyring")
    from_keyring = Settings.from_env(env, keyring=True).token
    assert from_keyring is not None and (from_keyring.workspace_id, from_keyring.source) == ("wsKeyring", "keyring")
    assert Settings.from_env({**env, "DIAGNOS_VAULT_URL": "https://staging"}, keyring=True).token is not None
    secure_keyring.items.clear()
    from_bao = Settings.from_env(env, keyring=True).token
    assert from_bao is not None and from_bao.workspace_id == "wsBao"
    assert from_bao.source == "OpenBao https://bao secret/team-a/token"


def test_an_explicit_mapping_never_reads_the_keyring_unless_asked(secure_keyring: MemoryKeyring) -> None:
    """🇺🇸 `Settings.from_env(env)` is hermetic; the CLI passes `keyring=True`. 🇧🇷 Hermético; a CLI pede o chaveiro."""
    secure_keyring.items[(SERVICE, VAULT)] = mint()
    with pytest.raises(ConfigError, match="No diagnos token found") as caught:
        Settings.from_env({})
    assert "diagnos login" in str(caught.value) and "DIAGNOS_TOKEN" in str(caught.value)
    assert Settings.from_env({}, keyring=True).token is not None


def test_an_insecure_keyring_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A token sitting in a plaintext backend is ignored, as if there were no keyring.

    🇧🇷 Um token num backend de texto puro é ignorado, como se não houvesse chaveiro.
    """
    backend = InsecureKeyring()
    backend.items[(SERVICE, VAULT)] = mint()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    with pytest.raises(ConfigError, match="No diagnos token found"):
        Settings.from_env({}, keyring=True)


def test_a_value_in_the_wrong_variable_names_the_right_one() -> None:
    """🇺🇸 A token in `DIAGNOS_API_TOKEN`, or an `apikey-` in `DIAGNOS_TOKEN`. 🇧🇷 Cada um na variável errada."""
    with pytest.raises(ConfigError, match="put it in DIAGNOS_TOKEN"):
        Settings.from_env({"DIAGNOS_API_TOKEN": mint()})
    with pytest.raises(TokenError, match="Put it in DIAGNOS_API_TOKEN"):
        Settings.from_env({"DIAGNOS_TOKEN": legacy_token()})


def test_an_explicit_token_replaces_discovery_and_keeps_the_rest_of_the_environment() -> None:
    """🇺🇸 `token=` (object, text or legacy text) wins; `DIAGNOS_VAULT_URL` still applies.

    🇧🇷 `token=` (objeto, texto ou texto legado) vence; o `DIAGNOS_VAULT_URL` continua valendo.
    """
    env = {"DIAGNOS_TOKEN": mint("wsEnv"), "DIAGNOS_VAULT_URL": "https://staging"}
    as_text = Settings.from_env(env, token=mint("wsArg"))
    assert as_text.token is not None and (as_text.token.workspace_id, as_text.token.source) == (
        "wsArg",
        "token= · --token",
    )
    assert as_text.vault_url == "https://staging"
    obj = DiagnosToken.parse(mint("wsObj"), source="mine")
    assert Settings.from_env(env, token=obj).token is obj
    legacy = Settings.from_env(env, token=legacy_token())
    assert (legacy.token, legacy.api_token is not None) == (None, True)


def test_openbao_refusing_or_unreachable_is_a_clear_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A denied read names the policy; an unreachable OpenBao names `OPENBAO_ADDR`; never the exception text.

    🇧🇷 Uma leitura negada cita a política; um OpenBao inalcançável cita `OPENBAO_ADDR`; nunca o texto da exceção.
    """
    env = {"OPENBAO_ADDR": "https://bao"}
    for failure, advice in ((hvac.exceptions.Forbidden, "policy"), (ConnectionError, "OPENBAO_ADDR")):
        fake = FakeOpenBao(fail_with=failure)
        monkeypatch.setattr(hvac, "Client", lambda fake=fake, **kwargs: fake)
        with pytest.raises(ConfigError, match=advice) as caught:
            Settings.from_env(env)
        assert "refused" not in str(caught.value)


def test_find_identity_skips_what_it_is_not_given() -> None:
    """🇺🇸 No keychain and no OpenBao: only the environment counts. 🇧🇷 Sem chaveiro e sem OpenBao: só o ambiente."""
    assert find_identity({}, vault_url=VAULT, keychain=None, openbao=None) == FoundIdentity()
    calls: list[Any] = []
    assert find_identity({}, vault_url=VAULT, keychain=Keychain(MemoryKeyring()), openbao=lambda: calls.append(1)) == (
        FoundIdentity()
    )
    assert calls == [1]


def test_without_token_reads_everything_but_the_identity() -> None:
    """🇺🇸 What `login`/`logout` need with no token anywhere. 🇧🇷 O que `login`/`logout` precisam sem token nenhum."""
    settings = Settings.without_token({"DIAGNOS_VAULT_URL": "https://staging", "OPENBAO_ADDR": "https://bao"})
    assert (settings.vault_url, settings.openbao_addr, settings.token, settings.api_token) == (
        "https://staging",
        "https://bao",
        None,
        None,
    )
    assert "token=None" in repr(settings)
