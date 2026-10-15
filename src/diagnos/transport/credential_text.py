"""🇺🇸 The text forms of the credential: the identity and key patterns, masking, and key-safe rejection.

Everything here that touches the key returns instead of raising, or receives
only a `SecretBox`: no traceback frame of this module can hold the key.

🇧🇷 As formas textuais da credencial: os padrões de identidade e chave, o mascaramento, e a recusa que protege a chave.

Tudo aqui que toca a chave retorna em vez de lançar, ou recebe só um
`SecretBox`: nenhum quadro de traceback deste módulo consegue guardar a chave.
"""

from __future__ import annotations

import re
from typing import Final, NoReturn

from diagnos.crypto.encoding import b64url_decode
from diagnos.crypto.secure import SecretBox
from diagnos.errors import ConfigError

IDENTITY_PATTERN: Final = re.compile(r"(?P<key_id>svc_[0-9a-f]{32})@(?P<workspace_id>[A-Za-z0-9_-]+)\.diagnos\.health")
# 🇺🇸 32 bytes = 42 × 6 + 4 bits: the last character carries 4 bits, so only 16 spellings are canonical (as the vault).
# 🇧🇷 32 bytes = 42 × 6 + 4 bits: o último caractere leva 4 bits, então só 16 grafias são canônicas (como no cofre).
SEED_PATTERN: Final = re.compile(r"[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]")
_FORMAT_HINT: Final = (
    "🇺🇸 Expected 'svc_<32 hex>@<workspace_id>.diagnos.health:<43-character base64url key>', exactly as the "
    "service account page showed it; copy it again in one piece. "
    "🇧🇷 Esperado 'svc_<32 hex>@<workspace_id>.diagnos.health:<chave base64url de 43 caracteres>', exatamente "
    "como a página da conta de serviço mostrou; copie de novo, inteira."
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


def refuse(source: str, problem: str) -> NoReturn:
    """🇺🇸 A `ConfigError` naming where the credential came from — never a byte of it.

    🇧🇷 Um `ConfigError` dizendo de onde a credencial veio — nunca um byte dela.
    """
    raise ConfigError(f"{source}: {problem} {_FORMAT_HINT}")


def reject_line(source: str, *, legacy: bool, separator: bool, seed: SecretBox | None) -> NoReturn:
    """🇺🇸 The first problem of a rejected line, as a `ConfigError`; the key never reaches here.

    🇧🇷 O primeiro problema de uma linha recusada, como `ConfigError`; a chave nunca chega aqui.
    """
    if seed is not None:
        seed.wipe()
    if legacy:
        raise ConfigError(
            f"🇺🇸 {source} holds a legacy 'apikey-' token. Put it in DIAGNOS_API_TOKEN (deprecated, accepted "
            "until 2027-04-15) or create a new credential: https://dev.diagnos.health/migrating "
            f"🇧🇷 {source} contém um token legado 'apikey-'. Coloque-o em DIAGNOS_API_TOKEN (obsoleto, aceito "
            "até 2027-04-15) ou crie uma credencial nova: https://dev.diagnos.health/migrating"
        )
    if not separator:
        refuse(source, "🇺🇸 there is no ':' before the key. 🇧🇷 não há ':' antes da chave.")
    if seed is None:
        refuse(source, BAD_SEED)
    refuse(source, "🇺🇸 the identity is malformed. 🇧🇷 a identidade está malformada.")


BAD_SEED: Final = (
    "🇺🇸 the key is not a canonical 43-character base64url Ed25519 seed. "
    "🇧🇷 a chave não é uma semente Ed25519 base64url canônica de 43 caracteres."
)


def take_seed(encoded: str) -> SecretBox | None:
    """🇺🇸 43 canonical base64url chars → a 32-byte `SecretBox`, else `None` — never raises, so no frame keeps the key.

    🇧🇷 43 caracteres base64url canônicos → um `SecretBox` de 32 bytes, senão `None` — nunca lança, então nenhum
    quadro guarda a chave.
    """
    if SEED_PATTERN.fullmatch(encoded) is None:
        return None
    return SecretBox.from_bytes(bytearray(b64url_decode(encoded)))
