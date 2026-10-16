"""🇺🇸 `DiagnosToken`: the service account token (`dgn_sk1_…`) — identity and vault key in one string.

The token is one line the browser shows once. It names the key
(`svc_<hex>`) and the workspace, and carries a 32-byte seed from which the
enclave derives everything (spec §3): Ed25519 + ML-DSA-65 to sign every
request, X25519 + ML-KEM-768 to open the session and the group keys sealed
to it. Parsing moves the seed straight into locked memory; after that, this
object hands out public keys, signatures and a copy of the seal pair —
never the seed. `repr`, `str`, pickling and every error are built so the
token text can never be printed.

🇧🇷 `DiagnosToken`: o token de conta de serviço (`dgn_sk1_…`) — identidade e chave do cofre numa string só.

O token é uma linha que o navegador mostra uma vez. Ele nomeia a chave
(`svc_<hex>`) e o workspace, e carrega uma semente de 32 bytes da qual o
enclave deriva tudo (spec §3): Ed25519 + ML-DSA-65 para assinar toda
requisição, X25519 + ML-KEM-768 para abrir a sessão e as chaves de grupo
seladas para ele. A leitura move a semente direto para memória travada;
depois disso, este objeto entrega chaves públicas, assinaturas e uma cópia do
par de selo — nunca a semente. `repr`, `str`, pickle e todo erro são feitos
para o texto do token nunca poder ser impresso.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, NoReturn, final

from diagnos.crypto import token_keys
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.errors import ConfigError

from .message_signature import identity_headers
from .signing import new_nonce
from .token_text import identity_of, refuse

if TYPE_CHECKING:
    import httpx

ENV_VAR: Final = "DIAGNOS_TOKEN"


@final
class DiagnosToken:
    """🇺🇸 A parsed service account token: key id and workspace in the clear, every key in the enclave.

    🇧🇷 Um token de conta de serviço lido: id da chave e workspace em claro, toda chave no enclave.
    """

    __slots__ = ("_key_id", "_keys", "_source", "_workspace_id")

    signs_requests: Final = True
    """🇺🇸 Every request carries a `created` timestamp. 🇧🇷 Toda requisição leva um timestamp `created`."""

    def __init__(self, key_id: str, workspace_id: str, keys: token_keys.TokenKeys, *, source: str) -> None:
        """🇺🇸 Use `parse()`; this only assembles already-checked parts. 🇧🇷 Use `parse()`; isto só junta partes."""
        self._key_id = key_id
        self._workspace_id = workspace_id
        self._keys = keys
        self._source = source

    @classmethod
    def parse(cls, text: str, *, source: str = ENV_VAR) -> DiagnosToken:
        """🇺🇸 Check the prefix and CRC, then derive the keys — a `TokenError` before any network call otherwise.

        🇧🇷 Confere o prefixo e o CRC, depois deriva as chaves — senão um `TokenError` antes de qualquer rede.
        """
        # 🇺🇸 Every local holding the text is deleted before any `raise`: a traceback renderer that prints frame
        #    locals (Sentry, rich, `cgitb`) must never find it.
        # 🇧🇷 Toda local com o texto é apagada antes de qualquer `raise`: um renderizador de traceback que imprime
        #    locais de quadro (Sentry, rich, `cgitb`) nunca pode achá-lo.
        stripped = text.strip()
        legacy = stripped.startswith("apikey-")
        decoded = token_keys.decode_token(stripped) if stripped and not legacy else "empty"
        del text, stripped
        if isinstance(decoded, str):
            refuse(source, "prefix" if legacy else decoded, legacy=legacy)
        key_id, seed, workspace_id = decoded
        del decoded
        try:
            keys = token_keys.TokenKeys.from_seed(seed)
        finally:
            seed.wipe()
        return cls(key_id, workspace_id, keys, source=source)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> DiagnosToken:
        """🇺🇸 `DIAGNOS_TOKEN` only; `Settings.from_env` also looks in the keyring and OpenBao.

        🇧🇷 Só `DIAGNOS_TOKEN`; o `Settings.from_env` também procura no chaveiro e no OpenBao.
        """
        text = (os.environ if env is None else env).get(ENV_VAR)
        if not text:
            raise ConfigError(
                f"🇺🇸 {ENV_VAR} is not set. 🇧🇷 {ENV_VAR} não está definida. https://dev.diagnos.health/authentication"
            )
        return cls.parse(text)

    @property
    def key_id(self) -> str:
        """🇺🇸 `svc_<32 hex>`: the signed `keyid`, and what an admin rotates or revokes.

        🇧🇷 `svc_<32 hex>`: o `keyid` assinado, e o que um admin gira ou revoga.
        """
        return self._key_id

    @property
    def workspace_id(self) -> str:
        """🇺🇸 The workspace the token belongs to. 🇧🇷 O workspace a que o token pertence."""
        return self._workspace_id

    @property
    def identity(self) -> str:
        """🇺🇸 `svc_<hex>@<workspace_id>.diagnos.health`, as the panel shows it. 🇧🇷 Como o painel mostra."""
        return identity_of(self._key_id, self._workspace_id)

    @property
    def source(self) -> str:
        """🇺🇸 Where it was read from: `DIAGNOS_TOKEN`, `keyring`, `OpenBao …`, `token=`. 🇧🇷 De onde foi lido."""
        return self._source

    @property
    def public_keys(self) -> dict[str, str]:
        """🇺🇸 The four public keys, base64url — what the vault registered; compare with the panel.

        🇧🇷 As quatro chaves públicas, base64url — o que o cofre registrou; compare com o painel.
        """
        return {
            "ed25519": b64url_encode(self._keys.ed25519_public),
            "ml_dsa_65": b64url_encode(self._keys.mldsa65_public),
            "x25519": b64url_encode(self._keys.x25519_public),
            "ml_kem_768": b64url_encode(self._keys.mlkem768_public),
        }

    @property
    def is_wiped(self) -> bool:
        """🇺🇸 Whether `wipe()` already ran. 🇧🇷 Se `wipe()` já rodou."""
        return self._keys.is_wiped

    def sign(self, message: bytes) -> bytes:
        """🇺🇸 `ed25519 ‖ ml-dsa-65` over `message` (3373 bytes), made in the enclave. 🇧🇷 Feita no enclave."""
        return self._keys.sign(message)

    def request_headers(self, method: str, url: httpx.URL, body: bytes, created: int) -> dict[str, str]:
        """🇺🇸 The RFC 9421 headers for one attempt — a fresh nonce every call, so a retry is never a replay.

        🇧🇷 Os headers RFC 9421 de uma tentativa — nonce novo a cada chamada, para retentar nunca ser replay.
        """
        return identity_headers(
            self.sign, keyid=self._key_id, method=method, url=url, body=body, created=created, nonce=new_nonce()
        )

    def keypair(self) -> HybridKeyPair:
        """🇺🇸 A locked copy of the X25519 + ML-KEM-768 pair, to open the session; its owner wipes it.

        🇧🇷 Uma cópia travada do par X25519 + ML-KEM-768, para abrir a sessão; quem a recebe a apaga.
        """
        return HybridKeyPair(self._keys.hybrid_keypair())

    def wipe(self) -> None:
        """🇺🇸 Zero every private key now; the token cannot sign afterwards. 🇧🇷 Zera toda chave privada agora."""
        self._keys.wipe()

    def __repr__(self) -> str:
        """🇺🇸 The identity, never the token. 🇧🇷 A identidade, nunca o token."""
        # 🇺🇸 A traceback may print a half-built instance. 🇧🇷 Um traceback pode imprimir uma instância incompleta.
        key_id = getattr(self, "_key_id", "svc_…")
        workspace_id = getattr(self, "_workspace_id", "…")
        return f"DiagnosToken(identity={identity_of(key_id, workspace_id)!r}, seed='<redacted>')"

    __str__ = __repr__

    def __reduce__(self) -> NoReturn:
        """🇺🇸 Never pickled: that would write the keys to disk. 🇧🇷 Nunca serializado: gravaria as chaves em disco."""
        raise TypeError("🇺🇸 DiagnosToken cannot be pickled. 🇧🇷 DiagnosToken não pode ser serializado.")

    def __copy__(self) -> NoReturn:
        """🇺🇸 One owner per set of keys. 🇧🇷 Um dono por conjunto de chaves."""
        raise TypeError("🇺🇸 DiagnosToken cannot be copied. 🇧🇷 DiagnosToken não pode ser copiado.")

    def __deepcopy__(self, memo: object) -> NoReturn:
        """🇺🇸 One owner per set of keys. 🇧🇷 Um dono por conjunto de chaves."""
        raise TypeError("🇺🇸 DiagnosToken cannot be copied. 🇧🇷 DiagnosToken não pode ser copiado.")
