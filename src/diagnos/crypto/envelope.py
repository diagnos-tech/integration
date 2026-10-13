"""🇺🇸 The single symmetric envelope of the product: HKDF-SHA256 + AES-256-GCM.

Mirrors the vault's reference envelope byte for byte (PROTOCOL §7).
Two purposes share this mechanism — wrapping a key and encrypting a
record — but keep separate public names on purpose, and now separate
*types* too: a wrapped key goes in and comes out as a `SecretBox` (it is
key material and never touches the Python heap), while content goes in and
comes out as `bytes` (it is the caller's data, meant to be read).

🇧🇷 O único envelope simétrico do produto: HKDF-SHA256 + AES-256-GCM.

Espelha o envelope de referência do cofre byte a byte (PROTOCOL §7).
Dois propósitos compartilham este mecanismo — embrulhar uma chave e cifrar
um registro — mas mantêm nomes públicos separados de propósito, e agora
*tipos* separados também: uma chave embrulhada entra e sai como
`SecretBox` (é material de chave e nunca toca o heap do Python), enquanto
conteúdo entra e sai como `bytes` (é dado de quem chama, feito para ser
lido).
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from diagnos.errors import CryptoError

from .encoding import b64url_decode, b64url_encode
from .hkdf import hkdf_sha256
from .secure import SecretBox, SecretLike, as_secret

SALT_LENGTH = 16
NONCE_LENGTH = 12
DERIVED_KEY_LENGTH = 32


@dataclass(frozen=True, slots=True)
class EncryptedPayload:
    """🇺🇸 The `{salt, nonce, ciphertext}` shape (all b64url) that crosses the wire.

    This is the only envelope shape in the protocol — a `HybridSeal` (§6)
    reuses these same three field names even though its `salt` carries a KEM
    encapsulation instead of an HKDF salt, so the wire JSON of both looks
    identical to anything that doesn't know the difference.

    🇧🇷 O formato `{salt, nonce, ciphertext}` (tudo b64url) que atravessa a rede.

    É o único formato de envelope do protocolo — um `HybridSeal` (§6) reusa
    os mesmos três nomes de campo mesmo com o `salt` carregando um
    encapsulamento KEM em vez de um salt de HKDF, então o JSON de ambos é
    idêntico para quem não sabe da diferença.
    """

    salt: str
    nonce: str
    ciphertext: str

    def to_dict(self) -> dict[str, str]:
        """🇺🇸 The exact JSON shape the vault expects. 🇧🇷 O formato de JSON exato que o cofre espera."""
        return {"salt": self.salt, "nonce": self.nonce, "ciphertext": self.ciphertext}

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> EncryptedPayload:
        """🇺🇸 Validates the three required fields before trusting the payload.

        A malformed response (missing field, wrong type) is a protocol bug or
        a corrupted transport, never a signal worth distinguishing from a bad
        key at decrypt time — so it raises the same `CryptoError`.

        🇧🇷 Valida os três campos obrigatórios antes de confiar no payload.

        Uma resposta malformada (campo faltando, tipo errado) é um bug de
        protocolo ou um transporte corrompido, nunca um sinal que vale a pena
        distinguir de uma chave errada na hora de decifrar — por isso lança o
        mesmo `CryptoError`.
        """
        try:
            salt, nonce, ciphertext = mapping["salt"], mapping["nonce"], mapping["ciphertext"]
        except KeyError as exc:
            raise CryptoError("EncryptedPayload: campo ausente (salt/nonce/ciphertext)") from exc
        if not (isinstance(salt, str) and isinstance(nonce, str) and isinstance(ciphertext, str)):
            raise CryptoError("EncryptedPayload: salt/nonce/ciphertext devem ser strings b64url")
        return cls(salt=salt, nonce=nonce, ciphertext=ciphertext)

    def decode(self) -> tuple[bytes, bytes, bytes]:
        """🇺🇸 The three fields as raw bytes; bad base64url is a `CryptoError` like any other failure to open.

        🇧🇷 Os três campos em bytes crus; base64url inválido é `CryptoError` como qualquer outra falha ao abrir.
        """
        try:
            return b64url_decode(self.salt), b64url_decode(self.nonce), b64url_decode(self.ciphertext)
        except ValueError as exc:
            raise CryptoError("envelope: salt/nonce/ciphertext não são b64url válidos") from exc


def _seal(wrapping_key: SecretLike, plaintext: bytes | SecretBox, info: str) -> EncryptedPayload:
    """🇺🇸 HKDF-derive a per-call subkey, then AES-256-GCM with no AAD.

    Deriving a fresh subkey per call (instead of using `wrapping_key`
    directly) means a random 16-byte salt, not nonce discipline alone, is
    what keeps two encryptions under the same wrapping key independent —
    cheap insurance against a nonce ever being reused.

    🇧🇷 Deriva uma subchave por chamada via HKDF, depois AES-256-GCM sem AAD.

    Derivar uma subchave nova a cada chamada (em vez de usar `wrapping_key`
    direto) faz um salt aleatório de 16 bytes, não só a disciplina de nonce,
    ser o que mantém duas cifragens sob a mesma chave de embrulho
    independentes — um seguro barato contra um nonce algum dia ser reusado.
    """
    salt = secrets.token_bytes(SALT_LENGTH)
    derived = hkdf_sha256(wrapping_key, info, DERIVED_KEY_LENGTH, salt)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    if isinstance(plaintext, SecretBox):
        ciphertext = derived.aes_gcm_seal_secret(nonce, plaintext)
    else:
        ciphertext = derived.aes_gcm_seal(nonce, plaintext)
    return EncryptedPayload(salt=b64url_encode(salt), nonce=b64url_encode(nonce), ciphertext=b64url_encode(ciphertext))


def _derived(wrapping_key: SecretLike, payload: EncryptedPayload, info: str) -> tuple[SecretBox, bytes, bytes]:
    """🇺🇸 The per-payload subkey plus the raw nonce/ciphertext. 🇧🇷 A subchave do payload mais nonce/ciphertext crus."""
    salt, nonce, ciphertext = payload.decode()
    return hkdf_sha256(wrapping_key, info, DERIVED_KEY_LENGTH, salt), nonce, ciphertext


def wrap_key(wrapping_key: SecretLike, key: SecretLike, info: str) -> EncryptedPayload:
    """🇺🇸 Encrypts a key under `wrapping_key`; the key never leaves the enclave to be sealed.

    🇧🇷 Cifra uma chave sob `wrapping_key`; a chave nunca sai do enclave para ser selada.
    """
    return _seal(wrapping_key, as_secret(key), info)


def unwrap_key(wrapping_key: SecretLike, payload: EncryptedPayload, info: str) -> SecretBox:
    """🇺🇸 The inverse of `wrap_key`; the unwrapped key is born inside a locked box.

    🇧🇷 O inverso de `wrap_key`; a chave desembrulhada nasce dentro de uma caixa travada.
    """
    derived, nonce, ciphertext = _derived(wrapping_key, payload, info)
    return derived.aes_gcm_open_secret(nonce, ciphertext)


def encrypt_content(dek: SecretLike, plaintext: bytes, info: str) -> EncryptedPayload:
    """🇺🇸 Encrypts a record (`plaintext` is document data) under a document DEK.

    Byte for byte the same operation as `wrap_key` — see the module
    docstring for why the name still differs.

    🇧🇷 Cifra um registro (`plaintext` é dado de documento) sob uma DEK de documento.

    Byte a byte a mesma operação que `wrap_key` — veja a docstring do módulo
    para o porquê do nome continuar diferente.
    """
    return _seal(dek, plaintext, info)


def decrypt_content(dek: SecretLike, payload: EncryptedPayload, info: str) -> bytes:
    """🇺🇸 The inverse of `encrypt_content`. 🇧🇷 O inverso de `encrypt_content`."""
    derived, nonce, ciphertext = _derived(dek, payload, info)
    return derived.aes_gcm_open(nonce, ciphertext)
