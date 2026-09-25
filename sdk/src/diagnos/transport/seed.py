"""🇺🇸 Opens `random_seed`, the vault's contribution to the SDK's entropy — inside the enclave.

`docs/PROTOCOL.md §4`: every response to a signed request carries
`random_seed: {"nonce", "ciphertext"}` in its JSON envelope — AES-256-GCM
under the session's `enc_key` with the session id as AAD (binding the seed to
*this* session so it cannot be replayed into another one), over
`{"seed": "<32 B b64url>"}`. It travels in the body, not in a header, so it
stays out of proxy logs and APM traces, which record headers and almost never
bodies. The SDK mixes it into its own randomness; it never trusts the vault's
contribution alone, so this module only has to recover the 32 bytes, not judge
whether they are safe to use by themselves. The decryption, the JSON parse and
the base64 decode all run in Rust: the seed is born as a `SecretBox` and never
exists on the Python heap.

🇧🇷 Abre `random_seed`, a contribuição do cofre para a entropia do SDK — dentro do enclave.

`docs/PROTOCOL.md §4`: toda resposta a uma requisição assinada leva
`random_seed: {"nonce", "ciphertext"}` no envelope JSON — AES-256-GCM sob o
`enc_key` da sessão com o id da sessão como AAD (prendendo a semente a *esta*
sessão para não poder ser reaproveitada em outra), sobre
`{"seed": "<32 B b64url>"}`. Viaja no corpo, não num header, para ficar fora
de log de proxy e de trace de APM, que registram headers e quase nunca corpos.
O SDK mistura isso à própria aleatoriedade; nunca confia sozinho na
contribuição do cofre, então este módulo só precisa recuperar os 32 bytes,
não julgar se são seguros por si só. A decifragem, o parse do JSON e a
decodificação do base64 rodam em Rust: a semente nasce como `SecretBox` e
nunca existe no heap do Python.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from diagnos.crypto.encoding import b64url_decode
from diagnos.crypto.secure import SecretBox, SecretLike, as_secret
from diagnos.errors import CryptoError

SEED_LENGTH = 32


def open_random_seed(enc_key: SecretLike, session_id: str, envelope: Mapping[str, Any]) -> SecretBox:
    """🇺🇸 Decrypt a `random_seed` envelope (`{"nonce", "ciphertext"}`) into a locked 32-byte box.

    Every failure mode — a missing field, bad base64url, a GCM tag that does
    not verify, JSON that is not the expected shape, a seed of the wrong
    length — collapses into `CryptoError`. Distinguishing "wrong key" from
    "tampered ciphertext" here would hand a decryption oracle to whoever is
    probing a live vault, so the ambiguity is deliberate, per `errors.py`.

    🇧🇷 Decifra um envelope `random_seed` (`{"nonce", "ciphertext"}`) numa caixa travada de 32 bytes.

    Todo jeito de falhar — campo faltando, base64url inválido, tag GCM que
    não confere, JSON fora da forma esperada, semente de tamanho errado —
    vira `CryptoError`. Distinguir "chave errada" de "ciphertext adulterado"
    aqui daria um oráculo de decifragem a quem estiver sondando um cofre de
    verdade, então a ambiguidade é de propósito, conforme `errors.py`.
    """
    try:
        nonce = b64url_decode(str(envelope["nonce"]))
        ciphertext = b64url_decode(str(envelope["ciphertext"]))
        seed = as_secret(enc_key).aes_gcm_open_json_field(nonce, ciphertext, session_id.encode("utf-8"), "seed")
        if len(seed) != SEED_LENGTH:
            raise ValueError(f"seed must be {SEED_LENGTH} bytes, got {len(seed)}")
        return seed
    except Exception as exc:
        raise CryptoError("random_seed did not open") from exc
