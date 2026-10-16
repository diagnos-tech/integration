"""🇺🇸 The token in the system keyring — only a backend that encrypts at rest counts as one.

`keyring` picks a backend per machine: the macOS Keychain, the Windows
Credential Locker, Secret Service or KWallet on Linux. It can also pick
backends that are not a keyring at all — `fail` and `null` store nothing,
and third-party ones such as `keyrings.alt` write a file on disk, plain or
wrapped in a password the same disk also holds. A token is a private key,
so this module trusts only the platform backends `keyring` itself ships and
treats everything else as "no keyring": the caller falls back to OpenBao or
refuses, and never writes a text file.

The `keyring` package comes with `diagnos[cli]`; without it, there is no
keyring here either.

🇧🇷 O token no chaveiro do sistema — só um backend que cifra em repouso conta como um.

O `keyring` escolhe um backend por máquina: o Keychain do macOS, o
Credential Locker do Windows, Secret Service ou KWallet no Linux. Ele também
pode escolher backends que não são chaveiro nenhum — `fail` e `null` não
guardam nada, e os de terceiros como o `keyrings.alt` gravam um arquivo em
disco, puro ou embrulhado numa senha que o mesmo disco também guarda. Um
token é uma chave privada, então este módulo só confia nos backends de
plataforma que o próprio `keyring` traz e trata todo o resto como "sem
chaveiro": quem chama cai para o OpenBao ou recusa, e nunca grava arquivo de
texto.

O pacote `keyring` vem com o `diagnos[cli]`; sem ele, aqui também não há
chaveiro.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from diagnos.errors import TokenStoreError

logger = logging.getLogger("diagnos")

SERVICE: Final = "diagnos"
"""🇺🇸 The keyring service name; the account is the vault URL, so staging and production never mix.

🇧🇷 O nome de serviço no chaveiro; a conta é a URL do cofre, para staging e produção nunca se misturarem.
"""
_PLATFORM: Final = "keyring.backends."
_NOT_A_KEYRING: Final = frozenset({"keyring.backends.fail.Keyring", "keyring.backends.null.Keyring"})
_CHAINER: Final = "keyring.backends.chainer.ChainerBackend"


def backend_name(backend: object) -> str:
    """🇺🇸 `module.Class` of a backend — what the messages and `whoami` show. 🇧🇷 `módulo.Classe` de um backend."""
    kind = type(backend)
    return f"{kind.__module__}.{kind.__qualname__}"


def is_secure(backend: object) -> bool:
    """🇺🇸 A platform backend `keyring` ships, or a chain made only of those; never `fail`, `null` or a file.

    🇧🇷 Um backend de plataforma que o `keyring` traz, ou uma cadeia só deles; nunca `fail`, `null` ou arquivo.
    """
    name = backend_name(backend)
    if name == _CHAINER:
        chained = list(getattr(backend, "backends", []))
        return bool(chained) and all(is_secure(inner) for inner in chained)
    return name.startswith(_PLATFORM) and name not in _NOT_A_KEYRING


class Keychain:
    """🇺🇸 Load, save and delete the token for one vault URL in the system keyring, if a secure one exists.

    🇧🇷 Carrega, grava e apaga o token de uma URL de cofre no chaveiro do sistema, se existir um seguro.
    """

    def __init__(self, backend: Any | None = None) -> None:
        """🇺🇸 `backend` for tests; by default `keyring.get_keyring()`, resolved on first use.

        🇧🇷 `backend` para testes; por padrão `keyring.get_keyring()`, resolvido no primeiro uso.
        """
        self._backend = backend
        self._errors: tuple[type[BaseException], ...] = ()

    def _resolve(self) -> Any | None:
        """🇺🇸 The backend, or `None` without the `keyring` package. 🇧🇷 O backend, ou `None` sem o pacote `keyring`."""
        try:
            import keyring
            import keyring.errors
        except ImportError:
            return self._backend
        self._errors = (keyring.errors.KeyringError,)
        if self._backend is None:
            self._backend = keyring.get_keyring()
        return self._backend

    @property
    def name(self) -> str:
        """🇺🇸 The backend in use, for messages; `none` without `keyring`. 🇧🇷 O backend em uso; `none` sem `keyring`."""
        backend = self._resolve()
        return "none" if backend is None else backend_name(backend)

    @property
    def secure(self) -> bool:
        """🇺🇸 Whether there is a keyring this module will store a token in. 🇧🇷 Se há um chaveiro seguro aqui."""
        backend = self._resolve()
        return backend is not None and is_secure(backend)

    def load(self, vault_url: str) -> str | None:
        """🇺🇸 The stored token, or `None` — also when the keyring is insecure, locked or unreachable.

        🇧🇷 O token guardado, ou `None` — também quando o chaveiro é inseguro, está travado ou inalcançável.
        """
        if not self.secure:
            return None
        try:
            value: str | None = self._resolve().get_password(SERVICE, vault_url)  # type: ignore[union-attr]
        except self._errors as exc:
            logger.debug("keyring %s could not be read: %s", self.name, type(exc).__name__)
            return None
        return value or None

    def save(self, vault_url: str, token: str) -> None:
        """🇺🇸 Stores the token, or `TokenStoreError` when there is no secure keyring or it refused.

        🇧🇷 Guarda o token, ou `TokenStoreError` quando não há chaveiro seguro ou ele recusou.
        """
        if not self.secure:
            raise TokenStoreError(
                f"🇺🇸 The system keyring ({self.name}) does not encrypt at rest; the token is not stored there. "
                f"🇧🇷 O chaveiro do sistema ({self.name}) não cifra em repouso; o token não é guardado nele."
            )
        try:
            self._resolve().set_password(SERVICE, vault_url, token)  # type: ignore[union-attr]
        except self._errors as exc:
            raise TokenStoreError(
                f"🇺🇸 The system keyring ({self.name}) refused to store the token ({type(exc).__name__}); unlock it "
                f"and try again. 🇧🇷 O chaveiro do sistema ({self.name}) recusou guardar o token "
                f"({type(exc).__name__}); destrave-o e tente de novo."
            ) from None

    def delete(self, vault_url: str) -> bool:
        """🇺🇸 Removes the stored token; `False` when there was none (or no secure keyring).

        🇧🇷 Remove o token guardado; `False` quando não havia (ou não há chaveiro seguro).
        """
        if self.load(vault_url) is None:
            return False
        try:
            self._resolve().delete_password(SERVICE, vault_url)  # type: ignore[union-attr]
        except self._errors as exc:
            logger.debug("keyring %s could not delete: %s", self.name, type(exc).__name__)
            return False
        return True
