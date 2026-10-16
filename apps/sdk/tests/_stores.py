"""🇺🇸 Stand-ins for the two token stores: a keyring backend and an OpenBao KV v2 client, both in memory.

`MemoryKeyring` poses as one of `keyring`'s own platform backends (its
`__module__` says so), because `Keychain` trusts only those;
`InsecureKeyring` keeps the module it was defined in, like any third-party
backend, and is refused. `FakeOpenBao` answers `hvac`'s
`secrets.kv.v2` calls from a dict, raising `hvac`'s own exceptions.

🇧🇷 Substitutos dos dois cofres de token: um backend de chaveiro e um client KV v2 do OpenBao, ambos em memória.

`MemoryKeyring` se passa por um dos backends de plataforma do próprio
`keyring` (o `__module__` diz isso), porque o `Keychain` só confia neles;
`InsecureKeyring` mantém o módulo onde foi definido, como qualquer backend de
terceiro, e é recusado. `FakeOpenBao` responde às chamadas
`secrets.kv.v2` do `hvac` a partir de um dict, lançando as próprias exceções
do `hvac`.
"""

from __future__ import annotations

from typing import Any

import hvac  # type: ignore[import-untyped]
from keyring.errors import KeyringLocked, PasswordDeleteError


class MemoryKeyring:
    """🇺🇸 A keyring in a dict that passes for a platform backend. 🇧🇷 Um chaveiro num dict, como de plataforma."""

    def __init__(self, *, locked: bool = False) -> None:
        """🇺🇸 Empty; `locked` makes every call fail as a locked keychain does. 🇧🇷 Vazio; `locked` faz tudo falhar."""
        self.items: dict[tuple[str, str], str] = {}
        self.locked = locked

    def _check(self) -> None:
        """🇺🇸 A locked keychain refuses. 🇧🇷 Um chaveiro travado recusa."""
        if self.locked:
            raise KeyringLocked("locked")

    def get_password(self, service: str, username: str) -> str | None:
        """🇺🇸 `keyring`'s read. 🇧🇷 A leitura do `keyring`."""
        self._check()
        return self.items.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        """🇺🇸 `keyring`'s write. 🇧🇷 A escrita do `keyring`."""
        self._check()
        self.items[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        """🇺🇸 `keyring`'s delete. 🇧🇷 A remoção do `keyring`."""
        if self.items.pop((service, username), None) is None:
            raise PasswordDeleteError("missing")


MemoryKeyring.__module__ = "keyring.backends.SecretService"


class InsecureKeyring(MemoryKeyring):
    """🇺🇸 The same dict, from a third-party module — what `keyrings.alt` looks like. 🇧🇷 O mesmo dict, de terceiro."""


InsecureKeyring.__module__ = "keyrings.alt.file"


class FakeOpenBao:
    """🇺🇸 `hvac.Client` reduced to `secrets.kv.v2` over a dict. 🇧🇷 O `hvac.Client` reduzido ao KV v2 num dict."""

    def __init__(self, *, fail_with: type[BaseException] | None = None) -> None:
        """🇺🇸 Empty; `fail_with` makes every call raise it. 🇧🇷 Vazio; `fail_with` faz toda chamada lançá-la."""
        self.data: dict[tuple[str, str], dict[str, Any]] = {}
        self.fail_with = fail_with
        self.secrets = self
        self.kv = self
        self.v2 = self

    def _check(self) -> None:
        """🇺🇸 Raise the configured failure. 🇧🇷 Lança a falha configurada."""
        if self.fail_with is not None:
            raise self.fail_with("refused")

    def read_secret_version(self, *, path: str, mount_point: str, raise_on_deleted_version: bool) -> dict[str, Any]:
        """🇺🇸 KV v2 read: `InvalidPath` when absent. 🇧🇷 Leitura KV v2: `InvalidPath` quando ausente."""
        self._check()
        if (mount_point, path) not in self.data:
            raise hvac.exceptions.InvalidPath("no secret")
        return {"data": {"data": dict(self.data[(mount_point, path)])}}

    def create_or_update_secret(self, *, path: str, secret: dict[str, Any], mount_point: str) -> None:
        """🇺🇸 KV v2 write. 🇧🇷 Escrita KV v2."""
        self._check()
        self.data[(mount_point, path)] = dict(secret)

    def delete_metadata_and_all_versions(self, *, path: str, mount_point: str) -> None:
        """🇺🇸 KV v2 delete. 🇧🇷 Remoção KV v2."""
        self._check()
        self.data.pop((mount_point, path), None)
