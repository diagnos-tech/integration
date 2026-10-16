"""🇺🇸 Where `save_token` puts a token: a secure keyring, else OpenBao, else nowhere — never a file.

The owner's rule, tested case by case: a plaintext or `null` keyring counts
as no keyring; OpenBao is the fallback when configured; with neither, the
refusal explains both options and `DIAGNOS_TOKEN`; and nothing is ever
written under the home directory.

🇧🇷 Onde o `save_token` põe um token: um chaveiro seguro, senão o OpenBao, senão nenhum lugar — nunca arquivo.

A regra do dono, testada caso a caso: um chaveiro de texto puro ou `null`
conta como sem chaveiro; o OpenBao é o plano B quando configurado; sem
nenhum dos dois, a recusa explica as duas opções e o `DIAGNOS_TOKEN`; e nada
é gravado no diretório do usuário.
"""

from __future__ import annotations

import sys
from pathlib import Path

import hvac  # type: ignore[import-untyped]
import pytest
from _stores import FakeOpenBao, InsecureKeyring, MemoryKeyring
from _tokens import mint
from keyring.backends import chainer, fail, null
from keyring.errors import PasswordDeleteError

from diagnos import ConfigError, Settings, TokenError, TokenStoreError, forget_token, save_token
from diagnos.token_store import SERVICE, Keychain, OpenBaoTokenStore, is_secure

VAULT = "https://vault.diagnos.health"
NO_BAO = Settings.without_token({})
WITH_BAO = Settings.without_token({"OPENBAO_ADDR": "https://bao", "OPENBAO_TOKEN": "s.writer"})


def test_only_platform_backends_count_as_a_keyring() -> None:
    """🇺🇸 `fail`, `null`, a third-party file backend and a chain holding one are all refused.

    🇧🇷 `fail`, `null`, um backend de arquivo de terceiro e uma cadeia com um deles são todos recusados.
    """
    assert is_secure(MemoryKeyring())
    for backend in (fail.Keyring(), null.Keyring(), InsecureKeyring()):
        assert not is_secure(backend), backend
    # 🇺🇸 `ChainerBackend.backends` is a class property over the installed backends; a stand-in names the members.
    # 🇧🇷 `ChainerBackend.backends` é uma propriedade de classe; um substituto nomeia os membros.
    for members, secure in (([MemoryKeyring()], True), ([MemoryKeyring(), InsecureKeyring()], False), ([], False)):
        chain = type("ChainerBackend", (), {"__module__": chainer.__name__, "backends": members})()
        assert is_secure(chain) is secure
    assert Keychain(InsecureKeyring()).name == "keyrings.alt.file.InsecureKeyring"


def test_a_secure_keyring_comes_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Keyring present and secure: stored there, under the vault URL, even with OpenBao configured.

    🇧🇷 Chaveiro presente e seguro: guardado nele, sob a URL do cofre, mesmo com OpenBao configurado.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    backend, bao = MemoryKeyring(), FakeOpenBao()
    text = mint()
    where = save_token(text, settings=WITH_BAO, keychain=Keychain(backend), openbao=_store(bao))
    assert where == "keyring (keyring.backends.SecretService.MemoryKeyring)"
    assert backend.items == {(SERVICE, VAULT): text}
    assert bao.data == {}
    assert list(tmp_path.iterdir()) == []


def test_without_a_secure_keyring_it_falls_back_to_openbao() -> None:
    """🇺🇸 A plaintext keyring is skipped and the token lands at `<prefix>/token` in OpenBao.

    🇧🇷 Um chaveiro de texto puro é pulado e o token vai para `<prefixo>/token` no OpenBao.
    """
    insecure, bao = InsecureKeyring(), FakeOpenBao()
    text = mint()
    where = save_token(text, settings=WITH_BAO, keychain=Keychain(insecure), openbao=_store(bao))
    assert where == "OpenBao https://bao secret/diagnos/token"
    assert insecure.items == {}
    assert bao.data[("secret", "diagnos/token")]["token"] == text
    assert _store(bao).load() == text
    assert save_token(text, settings=WITH_BAO, store="openbao", keychain=Keychain(MemoryKeyring()), openbao=_store(bao))


def test_with_neither_it_refuses_and_explains_both_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 No secure keyring, no OpenBao: `TokenStoreError` naming both, `DIAGNOS_TOKEN`, and no file.

    🇧🇷 Sem chaveiro seguro, sem OpenBao: `TokenStoreError` citando os dois, o `DIAGNOS_TOKEN`, e nenhum arquivo.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(TokenStoreError) as caught:
        save_token(mint(), settings=NO_BAO, keychain=Keychain(null.Keyring()))
    message = str(caught.value)
    for needle in ("keyring", "OPENBAO_ADDR", "DIAGNOS_TOKEN", "never written to a file", "nunca é gravado"):
        assert needle in message
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(TokenStoreError, match="--store openbao"):
        save_token(mint(), settings=WITH_BAO, store="keyring", keychain=Keychain(fail.Keyring()))


def test_a_token_pasted_wrong_is_never_stored() -> None:
    """🇺🇸 The CRC is checked before any store is touched. 🇧🇷 O CRC é conferido antes de tocar qualquer cofre."""
    backend = MemoryKeyring()
    with pytest.raises(TokenError, match="truncated"):
        save_token(mint()[:-4], settings=NO_BAO, keychain=Keychain(backend))
    assert backend.items == {}


def test_a_locked_keyring_or_a_refusing_openbao_is_a_clear_error() -> None:
    """🇺🇸 Store errors say what to do; their own text (which could echo the request) never shows.

    🇧🇷 Erros dos cofres dizem o que fazer; o texto deles (que poderia ecoar a requisição) nunca aparece.
    """
    with pytest.raises(TokenStoreError, match="unlock it"):
        save_token(mint(), settings=NO_BAO, keychain=Keychain(MemoryKeyring(locked=True)))
    with pytest.raises(Exception, match="may not write") as caught:
        save_token(
            mint(),
            settings=WITH_BAO,
            keychain=Keychain(fail.Keyring()),
            openbao=_store(FakeOpenBao(fail_with=hvac.exceptions.Forbidden)),
        )
    assert "refused" not in str(caught.value)
    assert Keychain(MemoryKeyring(locked=True)).load(VAULT) is None


def test_forget_removes_it_from_both_and_says_where(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `forget_token` deletes from the keyring and OpenBao; a second call finds nothing.

    🇧🇷 `forget_token` apaga do chaveiro e do OpenBao; uma segunda chamada não acha nada.
    """
    backend, bao = MemoryKeyring(), FakeOpenBao()
    backend.items[(SERVICE, VAULT)] = mint()
    _store(bao).save(mint())
    removed = forget_token(settings=WITH_BAO, keychain=Keychain(backend), openbao=_store(bao))
    assert removed == [
        "keyring (keyring.backends.SecretService.MemoryKeyring)",
        "OpenBao https://bao secret/diagnos/token",
    ]
    assert forget_token(settings=WITH_BAO, keychain=Keychain(backend), openbao=_store(bao)) == []
    assert forget_token(settings=NO_BAO, keychain=Keychain(null.Keyring())) == []
    monkeypatch.setattr(hvac, "Client", lambda **kwargs: bao)
    assert forget_token(settings=WITH_BAO, keychain=Keychain(MemoryKeyring())) == []


def test_openbao_ignores_a_record_of_another_version_and_needs_hvac(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A record of another version reads as empty; without `hvac` the error names the extra.

    🇧🇷 Um registro de outra versão lê como vazio; sem o `hvac`, o erro nomeia o extra.
    """
    bao = FakeOpenBao()
    bao.data[("secret", "diagnos/token")] = {"v": 2, "token": mint()}
    assert _store(bao).load() is None
    assert _store(bao).delete() is False
    monkeypatch.setitem(__import__("sys").modules, "hvac", None)
    with pytest.raises(Exception, match=r"diagnos\[openbao\]"):
        OpenBaoTokenStore(WITH_BAO)


class _StubbornKeyring(MemoryKeyring):
    """🇺🇸 Reads, but refuses to delete. 🇧🇷 Lê, mas recusa apagar."""

    def delete_password(self, service: str, username: str) -> None:
        """🇺🇸 Always refused. 🇧🇷 Sempre recusado."""
        raise PasswordDeleteError("refused")


_StubbornKeyring.__module__ = MemoryKeyring.__module__


class _StubbornOpenBao(FakeOpenBao):
    """🇺🇸 Reads and writes, but its policy forbids the delete. 🇧🇷 Lê e grava, mas a política proíbe apagar."""

    def delete_metadata_and_all_versions(self, *, path: str, mount_point: str) -> None:
        """🇺🇸 `Forbidden`, as a read-only token gets. 🇧🇷 `Forbidden`, como um token só de leitura recebe."""
        raise hvac.exceptions.Forbidden("denied")


def test_without_the_keyring_package_or_when_a_delete_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 No `keyring` installed is no keyring; a refused delete is `False` (keyring) or a `ConfigError` (OpenBao).

    🇧🇷 Sem o `keyring` instalado é sem chaveiro; uma remoção recusada é `False` (chaveiro) ou `ConfigError` (OpenBao).
    """
    stubborn = _StubbornKeyring()
    stubborn.items[(SERVICE, VAULT)] = mint()
    assert Keychain(stubborn).delete(VAULT) is False
    bao = _StubbornOpenBao()
    _store(bao).save(mint())
    with pytest.raises(ConfigError, match="may not delete"):
        _store(bao).delete()
    monkeypatch.setitem(sys.modules, "keyring", None)
    bare = Keychain()
    assert (bare.name, bare.secure, bare.load(VAULT)) == ("none", False, None)
    with pytest.raises(TokenStoreError, match="does not encrypt at rest"):
        bare.save(VAULT, mint())


def _store(bao: FakeOpenBao) -> OpenBaoTokenStore:
    """🇺🇸 The token store over the fake client. 🇧🇷 O cofre de token sobre o client falso."""
    return OpenBaoTokenStore(WITH_BAO, client=bao)
