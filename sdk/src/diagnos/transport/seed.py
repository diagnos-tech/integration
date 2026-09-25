"""🇺🇸 Opens `X-Session-Seed`, the vault's contribution to the SDK's entropy — inside the enclave.

`docs/PROTOCOL.md §4`: every signed response carries `<nonce>.<ciphertext>`,
AES-256-GCM under the session's `enc_key` with the session id as AAD (binding
the seed to *this* session so it cannot be replayed into another one), over
`{"seed": "<32 B b64url>"}`. The SDK mixes this into its own randomness; it
never trusts the vault's contribution alone, so this module only has to
recover the 32 bytes, not judge whether they are safe to use by themselves.
The decryption, the JSON parse and the base64 decode all run in Rust: the
seed is born as a `SecretBox` and never exists on the Python heap.

🇧🇷 Abre `X-Session-Seed`, a contribuição do cofre para a entropia do SDK — dentro do enclave.

`docs/PROTOCOL.md §4`: toda resposta assinada leva `<nonce>.<ciphertext>`,
AES-256-GCM sob o `enc_key` da sessão com o id da sessão como AAD (prendendo
a semente a *esta* sessão para não poder ser reaproveitada em outra), sobre
`{"seed": "<32 B b64url>"}`. O SDK mistura isso à própria aleatoriedade;
nunca confia sozinho na contribuição do cofre, então este módulo só precisa
recuperar os 32 bytes, não julgar se são seguros por si só. A decifragem, o
parse do JSON e a decodificação do base64 rodam em Rust: a semente nasce
como `SecretBox` e nunca existe no heap do Python.
"""

from __future__ import annotations

from diagnos.crypto.encoding import b64url_decode
from diagnos.crypto.secure import SecretBox, SecretLike, as_secret
from diagnos.errors import CryptoError

SEED_LENGTH = 32


def open_session_seed(enc_key: SecretLike, session_id: str, header_value: str) -> SecretBox:
    """🇺🇸 Decrypt an `X-Session-Seed` header value into a locked 32-byte box.

    Every failure mode — bad separator, bad base64url, a GCM tag that does
    not verify, JSON that is not the expected shape, a seed of the wrong
    length — collapses into `CryptoError`. Distinguishing "wrong key" from
    "tampered ciphertext" here would hand a decryption oracle to whoever is
    probing a live vault, so the ambiguity is deliberate, per `errors.py`.

    🇧🇷 Decifra o valor de um header `X-Session-Seed` numa caixa travada de 32 bytes.

    Todo jeito de falhar — separador errado, base64url inválido, tag GCM que
    não confere, JSON fora da forma esperada, semente de tamanho errado —
    vira `CryptoError`. Distinguir "chave errada" de "ciphertext adulterado"
    aqui daria um oráculo de decifragem a quem estiver sondando um cofre de
    verdade, então a ambiguidade é de propósito, conforme `errors.py`.
    """
    try:
        nonce_part, separator, ciphertext_part = header_value.partition(".")
        if not separator:
            raise ValueError("X-Session-Seed has no '.' separator")
        nonce = b64url_decode(nonce_part)
        ciphertext = b64url_decode(ciphertext_part)
        seed = as_secret(enc_key).aes_gcm_open_json_field(nonce, ciphertext, session_id.encode("utf-8"), "seed")
        if len(seed) != SEED_LENGTH:
            raise ValueError(f"seed must be {SEED_LENGTH} bytes, got {len(seed)}")
        return seed
    except Exception as exc:
        raise CryptoError("X-Session-Seed did not open") from exc
