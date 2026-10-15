"""🇺🇸 `ServiceAccountCredential`: the SDK's identity — an Ed25519 key named `svc_<hex>@<workspace>.diagnos.health`.

The key pair is born in the browser of whoever creates the service account;
the vault keeps only the public half. What reaches this SDK is the identity
plus the 32-byte seed, as one line (`DIAGNOS_CREDENTIAL`, split on the LAST
`:`) or as the JSON file downloaded at creation (`credential_file.py`). The
seed moves into a `SecretBox` the moment it is parsed and is only ever used
inside the enclave to sign (`message_signature.py`); `repr`, `str`, pickling
and every error message here are built so it can never be printed.

🇧🇷 `ServiceAccountCredential`: a identidade do SDK — uma chave Ed25519 chamada `svc_<hex>@<workspace>.diagnos.health`.

O par de chaves nasce no navegador de quem cria a conta de serviço; o cofre
guarda só a metade pública. O que chega a este SDK é a identidade mais a
semente de 32 bytes, numa linha só (`DIAGNOS_CREDENTIAL`, dividida no ÚLTIMO
`:`) ou no JSON baixado na criação (`credential_file.py`). A semente vai para
um `SecretBox` no instante em que é lida e só é usada dentro do enclave para
assinar (`message_signature.py`); `repr`, `str`, pickle e toda mensagem de erro
daqui são feitos para ela nunca poder ser impressa.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, NoReturn, final

from diagnos.crypto import ed25519
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.errors import ConfigError

from .credential_text import IDENTITY_PATTERN, mask_identity, refuse, reject_line, take_seed
from .message_signature import identity_headers
from .signing import new_nonce

if TYPE_CHECKING:
    import httpx

NOT_CONFIGURED: Final = (
    "🇺🇸 No diagnos credential found. Set DIAGNOS_CREDENTIAL to the line the service account page showed "
    "('svc_…@<workspace>.diagnos.health:<key>'), or DIAGNOS_CREDENTIALS_FILE to the downloaded JSON, or save that "
    "file as ~/.config/diagnos/credentials.json. Create one under Settings → Service accounts. "
    "🇧🇷 Nenhuma credencial diagnos encontrada. Defina DIAGNOS_CREDENTIAL com a linha que a página da conta de "
    "serviço mostrou ('svc_…@<workspace>.diagnos.health:<chave>'), ou DIAGNOS_CREDENTIALS_FILE com o JSON baixado, "
    "ou salve esse arquivo como ~/.config/diagnos/credentials.json. Crie uma em Configurações → Contas de serviço."
)


@final
class ServiceAccountCredential:
    """🇺🇸 A parsed service account credential: identity in the clear, seed locked in the enclave.

    🇧🇷 Uma credencial de conta de serviço lida: identidade em claro, semente travada no enclave.
    """

    __slots__ = ("_identity", "_key_id", "_public_key", "_seed", "_service_account", "_source", "_workspace_id")

    signs_requests: Final = True
    """🇺🇸 Every request carries a `created` timestamp. 🇧🇷 Toda requisição leva um timestamp `created`."""

    def __init__(self, identity: str, seed: SecretBox, *, service_account: str | None = None, source: str = "") -> None:
        """🇺🇸 Validates `identity` and derives the public key (which also checks the seed is 32 bytes).

        🇧🇷 Valida `identity` e deriva a chave pública (o que também confere que a semente tem 32 bytes).
        """
        where = source or "credential · credencial"
        match = IDENTITY_PATTERN.fullmatch(identity)
        if match is None:
            refuse(where, "🇺🇸 the identity is malformed. 🇧🇷 a identidade está malformada.")
        if len(seed) != ed25519.SEED_BYTES:
            refuse(where, "🇺🇸 the private key is not 32 bytes. 🇧🇷 a chave privada não tem 32 bytes.")
        self._identity = identity
        self._key_id = match["key_id"]
        self._workspace_id = match["workspace_id"]
        self._seed = seed
        self._public_key = b64url_encode(ed25519.public_key(seed))
        self._service_account = service_account
        self._source = where

    @classmethod
    def parse(cls, text: str, *, source: str = "DIAGNOS_CREDENTIAL") -> ServiceAccountCredential:
        """🇺🇸 Parse `<identity>:<seed>`, split on the last `:` (the identity never contains one).

        🇧🇷 Lê `<identidade>:<semente>`, dividindo no último `:` (a identidade nunca tem um).
        """
        # 🇺🇸 Every local that holds the key is deleted before any `raise`: a traceback renderer that prints
        #    frame locals (Sentry, rich, `cgitb`) must never find it.
        # 🇧🇷 Toda local que guarda a chave é apagada antes de qualquer `raise`: um renderizador de traceback
        #    que imprime locais de quadro (Sentry, rich, `cgitb`) nunca pode achá-la.
        legacy = text.lstrip().startswith("apikey-")
        identity, separator, encoded = text.strip().rpartition(":")
        del text
        seed = take_seed(encoded) if separator and not legacy else None
        del encoded
        if legacy or seed is None or IDENTITY_PATTERN.fullmatch(identity) is None:
            # 🇺🇸 Swapped halves would leave the key in `identity`. 🇧🇷 Trocadas, a chave ficaria em `identity`.
            del identity
            reject_line(source, legacy=legacy, separator=bool(separator), seed=seed)
        return cls(identity, seed, source=source)

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> ServiceAccountCredential:
        """🇺🇸 Load the JSON file downloaded when the credential was created. 🇧🇷 Carrega o JSON baixado na criação."""
        from .credential_file import credential_from_file

        return credential_from_file(path)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ServiceAccountCredential:
        """🇺🇸 `DIAGNOS_CREDENTIAL`, else `DIAGNOS_CREDENTIALS_FILE`, else `~/.config/diagnos/credentials.json`.

        🇧🇷 `DIAGNOS_CREDENTIAL`, senão `DIAGNOS_CREDENTIALS_FILE`, senão `~/.config/diagnos/credentials.json`.
        """
        from .credential_file import find_identity

        found = find_identity(os.environ if env is None else env)
        if found.credential is None:
            raise ConfigError(NOT_CONFIGURED)
        return found.credential

    @property
    def identity(self) -> str:
        """🇺🇸 `svc_<hex>@<workspace_id>.diagnos.health` — the `keyid` of every signature.

        🇧🇷 `svc_<hex>@<workspace_id>.diagnos.health` — o `keyid` de toda assinatura.
        """
        return self._identity

    @property
    def key_id(self) -> str:
        """🇺🇸 `svc_<hex>`: what an admin rotates or revokes. 🇧🇷 `svc_<hex>`: o que um admin gira ou revoga."""
        return self._key_id

    @property
    def workspace_id(self) -> str:
        """🇺🇸 The workspace the key belongs to. 🇧🇷 O workspace a que a chave pertence."""
        return self._workspace_id

    @property
    def service_account(self) -> str | None:
        """🇺🇸 The account's name, when the credential file carries it. 🇧🇷 O nome da conta, quando o arquivo o traz."""
        return self._service_account

    @property
    def public_key(self) -> str:
        """🇺🇸 The public key, base64url (43 chars) — compare it with the panel's. 🇧🇷 A chave pública, base64url."""
        return self._public_key

    @property
    def source(self) -> str:
        """🇺🇸 Where it was read from (env var or file path). 🇧🇷 De onde foi lida (variável ou caminho)."""
        return self._source

    def sign(self, message: bytes) -> bytes:
        """🇺🇸 Ed25519 signature of `message`, made in the enclave. 🇧🇷 Assinatura Ed25519, feita no enclave."""
        return ed25519.sign(self._seed, message)

    def request_headers(self, method: str, url: httpx.URL, body: bytes, created: int) -> dict[str, str]:
        """🇺🇸 The RFC 9421 headers for one attempt — a fresh nonce every call, so a retry is never a replay.

        🇧🇷 Os headers RFC 9421 de uma tentativa — nonce novo a cada chamada, para retentar nunca ser replay.
        """
        return identity_headers(
            self.sign, keyid=self._identity, method=method, url=url, body=body, created=created, nonce=new_nonce()
        )

    def wipe(self) -> None:
        """🇺🇸 Zero the seed now; it cannot sign afterwards. 🇧🇷 Zera a semente agora; depois não assina."""
        self._seed.wipe()

    def __repr__(self) -> str:
        """🇺🇸 Masked identity, never the key. 🇧🇷 Identidade mascarada, nunca a chave."""
        # 🇺🇸 A traceback may print a half-built instance. 🇧🇷 Um traceback pode imprimir uma instância incompleta.
        identity = mask_identity(getattr(self, "_identity", ""))
        return f"ServiceAccountCredential(identity={identity!r}, private_key='<redacted>')"

    __str__ = __repr__

    def __reduce__(self) -> NoReturn:
        """🇺🇸 Never pickled: that would write the seed to disk. 🇧🇷 Nunca serializada: gravaria a semente em disco."""
        raise TypeError(
            "🇺🇸 ServiceAccountCredential cannot be pickled. 🇧🇷 ServiceAccountCredential não pode ser serializada."
        )
