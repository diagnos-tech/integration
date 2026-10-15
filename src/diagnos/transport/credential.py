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
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, NoReturn, final

from diagnos.crypto import ed25519
from diagnos.crypto.encoding import b64url_decode, b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.errors import ConfigError

from .message_signature import identity_headers
from .signing import new_nonce

if TYPE_CHECKING:
    import httpx

IDENTITY_PATTERN: Final = re.compile(r"(?P<key_id>svc_[0-9a-f]{32})@(?P<workspace_id>[A-Za-z0-9_-]+)\.diagnos\.health")
SEED_PATTERN: Final = re.compile(r"[A-Za-z0-9_-]{43}")
_FORMAT_HINT: Final = (
    "🇺🇸 Expected 'svc_<32 hex>@<workspace_id>.diagnos.health:<43-character base64url key>', exactly as the "
    "service account page showed it; copy it again in one piece. "
    "🇧🇷 Esperado 'svc_<32 hex>@<workspace_id>.diagnos.health:<chave base64url de 43 caracteres>', exatamente "
    "como a página da conta de serviço mostrou; copie de novo, inteira."
)

NOT_CONFIGURED: Final = (
    "🇺🇸 No diagnos credential found. Set DIAGNOS_CREDENTIAL to the line the service account page showed "
    "('svc_…@<workspace>.diagnos.health:<key>'), or DIAGNOS_CREDENTIALS_FILE to the downloaded JSON, or save that "
    "file as ~/.config/diagnos/credentials.json. Create one under Settings → Service accounts. "
    "🇧🇷 Nenhuma credencial diagnos encontrada. Defina DIAGNOS_CREDENTIAL com a linha que a página da conta de "
    "serviço mostrou ('svc_…@<workspace>.diagnos.health:<chave>'), ou DIAGNOS_CREDENTIALS_FILE com o JSON baixado, "
    "ou salve esse arquivo como ~/.config/diagnos/credentials.json. Crie uma em Configurações → Contas de serviço."
)


def mask_identity(identity: str) -> str:
    """🇺🇸 `svc_1a2b…9f0e@ws.diagnos.health`: enough to tell keys apart, not enough to name one in a request.

    🇧🇷 `svc_1a2b…9f0e@ws.diagnos.health`: o bastante para diferenciar chaves, não para nomear uma numa requisição.
    """
    match = IDENTITY_PATTERN.fullmatch(identity)
    if match is None:
        return "svc_…"
    key_id = match["key_id"]
    return f"{key_id[:8]}…{key_id[-4:]}@{match['workspace_id']}.diagnos.health"


def _refuse(source: str, problem: str) -> NoReturn:
    """🇺🇸 A `ConfigError` naming where the credential came from — never a byte of it.

    🇧🇷 Um `ConfigError` dizendo de onde a credencial veio — nunca um byte dela.
    """
    raise ConfigError(f"{source}: {problem} {_FORMAT_HINT}")


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
            _refuse(where, "🇺🇸 the identity is malformed. 🇧🇷 a identidade está malformada.")
        if len(seed) != ed25519.SEED_BYTES:
            _refuse(where, "🇺🇸 the private key is not 32 bytes. 🇧🇷 a chave privada não tem 32 bytes.")
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
        value = text.strip()
        if value.startswith("apikey-"):
            raise ConfigError(
                f"🇺🇸 {source} holds a legacy 'apikey-' token. Put it in DIAGNOS_API_TOKEN (deprecated, accepted "
                "until 2027-04-15) or create a new credential: https://dev.diagnos.health/migrating "
                f"🇧🇷 {source} contém um token legado 'apikey-'. Coloque-o em DIAGNOS_API_TOKEN (obsoleto, aceito "
                "até 2027-04-15) ou crie uma credencial nova: https://dev.diagnos.health/migrating"
            )
        identity, separator, encoded = value.rpartition(":")
        if not separator:
            _refuse(source, "🇺🇸 there is no ':' before the key. 🇧🇷 não há ':' antes da chave.")
        return cls(identity, _seed_from_b64url(encoded, source=source), source=source)

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
        return f"ServiceAccountCredential(identity={mask_identity(self._identity)!r}, private_key='<redacted>')"

    __str__ = __repr__

    def __reduce__(self) -> NoReturn:
        """🇺🇸 Never pickled: that would write the seed to disk. 🇧🇷 Nunca serializada: gravaria a semente em disco."""
        raise TypeError(
            "🇺🇸 ServiceAccountCredential cannot be pickled. 🇧🇷 ServiceAccountCredential não pode ser serializada."
        )


def _seed_from_b64url(encoded: str, *, source: str) -> SecretBox:
    """🇺🇸 43 base64url chars → a 32-byte `SecretBox`; the transient `bytearray` is zeroed by the move.

    🇧🇷 43 caracteres base64url → um `SecretBox` de 32 bytes; o `bytearray` transitório é zerado na mudança.
    """
    if SEED_PATTERN.fullmatch(encoded) is None:
        _refuse(source, "🇺🇸 the key is not 43 base64url characters. 🇧🇷 a chave não tem 43 caracteres base64url.")
    return SecretBox.from_bytes(bytearray(b64url_decode(encoded)))
