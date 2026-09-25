"""🇺🇸 HKDF-SHA256 (RFC 5869) — the single key-derivation primitive of the SDK, run inside the enclave.

🇧🇷 HKDF-SHA256 (RFC 5869) — a única primitiva de derivação de chave do SDK, executada dentro do enclave.
"""

from __future__ import annotations

from .secure import SecretBox, SecretLike, as_secret

DEFAULT_LENGTH = 32


def hkdf_sha256(
    ikm: SecretLike, info: bytes | str, length: int = DEFAULT_LENGTH, salt: bytes | None = None
) -> SecretBox:
    """🇺🇸 Derive `length` bytes from `ikm` with domain separation by `info`; the result is a new locked box.

    `info` is the only thing standing between two uses of the same input key
    material producing the same output key — every caller passes a versioned
    string (`imgexam-<purpose>-v1`) so a future change of meaning never
    silently reuses a key. The `imgexam-` prefix is historical and frozen:
    these bytes are baked into every ciphertext already stored, so they are
    wire constants, not branding (`docs/PROTOCOL.md`, "Frozen labels"). A `str` `info` is encoded as UTF-8, matching the
    vault's TypeScript reference implementation, which does the same
    before calling `@noble/hashes`. `salt=None` is RFC 5869's "no salt"
    case (an all-zero salt of hash length), not a shortcut we invented.

    🇧🇷 Deriva `length` bytes de `ikm` com separação de domínio por `info`; o resultado é uma caixa travada nova.

    `info` é a única coisa que separa dois usos do mesmo material de entrada
    de produzirem a mesma chave de saída — todo chamador passa uma string
    versionada (`imgexam-<propósito>-v1`) para que uma mudança futura de
    significado nunca reuse uma chave em silêncio. O prefixo `imgexam-` é
    histórico e congelado: estes bytes estão em todo ciphertext já gravado,
    então são constantes de fio, não marca (`docs/PROTOCOL.pt-BR.md`,
    "Rótulos congelados"). Um `info` do tipo `str` é
    codificado em UTF-8, espelhando a implementação de referência do cofre
    em TypeScript, que faz o mesmo antes de chamar
    `@noble/hashes`. `salt=None` é o caso "sem salt" da RFC 5869 (um salt de
    zeros do tamanho do hash), não um atalho que inventamos.
    """
    info_bytes = info.encode("utf-8") if isinstance(info, str) else info
    return as_secret(ikm).hkdf_sha256(info=info_bytes, length=length, salt=salt)
