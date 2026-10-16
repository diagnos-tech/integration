"""🇺🇸 The token in OpenBao — where a server keeps it, and where a workstation without a secure keyring does.

One KV v2 secret, `<OPENBAO_PATH_PREFIX>/token` under `OPENBAO_MOUNT`
(`secret/diagnos/token` by default), next to the auto-unseal session the SDK
already saves there (`session/unseal.py`) and reached with the same
`OPENBAO_*` settings. The path is fixed rather than derived from the token,
because whoever reads it does not have the token yet; one deployment, one
prefix, one token. The policy decides who may do what: the API's runtime
token only `read`s it, and storing or rotating it takes a writer token
(`apps/api/deploy/compose/openbao/`).

🇧🇷 O token no OpenBao — onde um servidor o guarda, e onde uma estação sem chaveiro seguro guarda.

Um segredo KV v2, `<OPENBAO_PATH_PREFIX>/token` sob `OPENBAO_MOUNT`
(`secret/diagnos/token` por padrão), ao lado da sessão de auto-unseal que o
SDK já salva lá (`session/unseal.py`) e alcançado com as mesmas
configurações `OPENBAO_*`. O caminho é fixo em vez de derivado do token,
porque quem o lê ainda não tem o token; um deployment, um prefixo, um token.
A política decide quem faz o quê: o token de execução da API só `read`, e
guardar ou girar exige um token de escrita (`apps/api/deploy/compose/openbao/`).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Final

from diagnos.errors import ConfigError

if TYPE_CHECKING:
    from diagnos.transport.config import Settings

TOKEN_KEY: Final = "token"  # noqa: S105 — the KV field's name, not a secret
_VERSION: Final = 1


def location(settings: Settings) -> str:
    """🇺🇸 `OpenBao <addr> <mount>/<prefix>/token` — where, for messages and `whoami`. 🇧🇷 Onde, para mensagens."""
    return f"OpenBao {settings.openbao_addr} {settings.openbao_mount}/{settings.openbao_path_prefix}/{TOKEN_KEY}"


class OpenBaoTokenStore:
    """🇺🇸 Load, save and delete the token at `<mount>/<prefix>/token`. 🇧🇷 Carrega, grava e apaga o token no OpenBao."""

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        """🇺🇸 `hvac` comes with `diagnos[openbao]`; imported here so the SDK never needs it otherwise.

        🇧🇷 O `hvac` vem com o `diagnos[openbao]`; importado aqui para o SDK nunca precisar dele fora isso.
        """
        try:
            import hvac  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ConfigError(
                "🇺🇸 Reading the token from OpenBao needs 'hvac': pip install \"diagnos[openbao]\". "
                "🇧🇷 Ler o token do OpenBao precisa do 'hvac': pip install \"diagnos[openbao]\"."
            ) from exc
        self._missing: type[BaseException] = hvac.exceptions.InvalidPath
        self._forbidden: type[BaseException] = hvac.exceptions.Forbidden
        self._client = client or hvac.Client(
            url=settings.openbao_addr, token=settings.openbao_token, namespace=settings.openbao_namespace
        )
        self._mount = settings.openbao_mount
        self._path = f"{settings.openbao_path_prefix}/{TOKEN_KEY}"
        self.location = location(settings)
        """🇺🇸 Where, for messages and `whoami`. 🇧🇷 Onde, para mensagens e `whoami`."""

    def _refused(self, action: str, exc: BaseException) -> ConfigError:
        """🇺🇸 One message for a denied or unreachable OpenBao — the exception's class, never its text.

        🇧🇷 Uma mensagem para OpenBao negado ou inalcançável — a classe da exceção, nunca o texto dela.
        """
        if isinstance(exc, self._forbidden):
            return ConfigError(
                f"🇺🇸 {self.location}: the OpenBao token may not {action} the diagnos token; grant it in the policy "
                f"(`policy.hcl`). 🇧🇷 {self.location}: o token do OpenBao não pode {action} o token do diagnos; "
                "conceda na política (`policy.hcl`)."
            )
        return ConfigError(
            f"🇺🇸 {self.location}: could not {action} the diagnos token ({type(exc).__name__}); check OPENBAO_ADDR "
            f"and that OpenBao is unsealed. 🇧🇷 {self.location}: não foi possível {action} o token do diagnos "
            f"({type(exc).__name__}); confira OPENBAO_ADDR e se o OpenBao está desselado."
        )

    def load(self) -> str | None:
        """🇺🇸 The stored token, or `None` when nothing is stored; a denied or unreachable OpenBao is a `ConfigError`.

        🇧🇷 O token guardado, ou `None` quando nada está guardado; OpenBao negado ou inalcançável é `ConfigError`.
        """
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=self._path, mount_point=self._mount, raise_on_deleted_version=True
            )
        except self._missing:
            return None
        except Exception as exc:
            raise self._refused("read", exc) from None
        data = response.get("data", {}).get("data", {})
        token = data.get(TOKEN_KEY) if data.get("v") == _VERSION else None
        return token if isinstance(token, str) and token else None

    def save(self, token: str) -> None:
        """🇺🇸 Stores (or replaces) the token. 🇧🇷 Guarda (ou substitui) o token."""
        try:
            self._client.secrets.kv.v2.create_or_update_secret(
                path=self._path,
                secret={"v": _VERSION, TOKEN_KEY: token, "saved_at": int(time.time())},
                mount_point=self._mount,
            )
        except Exception as exc:
            del token
            raise self._refused("write", exc) from None

    def delete(self) -> bool:
        """🇺🇸 Removes the token and its versions; `False` when there was none.

        🇧🇷 Remove o token e as versões dele; `False` quando não havia.
        """
        if self.load() is None:
            return False
        try:
            self._client.secrets.kv.v2.delete_metadata_and_all_versions(path=self._path, mount_point=self._mount)
        except Exception as exc:
            raise self._refused("delete", exc) from None
        return True
