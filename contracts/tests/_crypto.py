"""🇺🇸 Deterministic stand-ins for the vault's side of the cryptography, so the contract file never churns.

A Pact file records the *examples* each interaction was defined with. The
examples the SDK has to actually open — a sealed session, a sealed group key,
an `X-Session-Seed`, an encrypted record — must therefore be real ciphertext
under keys the test controls, and they must come out byte-identical on every
run, or `contracts/diagnos-sdk-diagnos-vault.json` would change on every
`make contract` without the contract having changed at all.

So every random input the protocol normally draws (ephemeral X25519 secret,
ML-KEM encapsulation coin, HKDF salt, AES-GCM nonce) is derived here from a
fixed label with SHA-256. This is a test oracle, never a pattern to copy:
reusing a nonce under a real key is exactly what the SDK is built to never do.
Only `pynacl`, `kyber-py` and `cryptography` are used — independent
implementations, so a contract test that passes also cross-checks the Rust
enclave against a second implementation of `docs/PROTOCOL.md §4–§7`.

🇧🇷 Substitutos determinísticos do lado do cofre na criptografia, para o arquivo de contrato nunca mudar à toa.

Um arquivo Pact grava os *exemplos* com que cada interação foi definida. Os
exemplos que o SDK precisa de fato abrir — uma sessão selada, uma chave de
grupo selada, um `X-Session-Seed`, um registro cifrado — precisam então ser
ciphertext de verdade sob chaves que o teste controla, e precisam sair
idênticos byte a byte em toda rodada, senão
`contracts/diagnos-sdk-diagnos-vault.json` mudaria a cada `make contract` sem
o contrato ter mudado nada.

Por isso toda entrada aleatória que o protocolo normalmente sorteia (secreta
X25519 efêmera, moeda do encapsulamento ML-KEM, salt do HKDF, nonce do
AES-GCM) é derivada aqui de um rótulo fixo com SHA-256. Isto é um oráculo de
teste, nunca um padrão a copiar: reusar nonce sob uma chave de verdade é
exatamente o que o SDK foi feito para nunca fazer. Só `pynacl`, `kyber-py` e
`cryptography` são usados — implementações independentes, então um teste de
contrato que passa também confere o enclave Rust contra uma segunda
implementação de `docs/PROTOCOL.md §4–§7`.
"""

from __future__ import annotations

import base64
import hashlib
import json

import nacl.bindings as nb
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from diagnos.crypto.hybrid import HybridKeyPair
from kyber_py.ml_kem import ML_KEM_768

# 🇺🇸 Frozen wire constant (`docs/PROTOCOL.md §6`) — the `imgexam-` prefix is historical.
# 🇧🇷 Constante de fio congelada (`docs/PROTOCOL.md §6`) — o prefixo `imgexam-` é histórico.
HYBRID_SEAL_INFO = b"imgexam-sdk-hybrid-seal-v1"


def fixed_bytes(label: str, length: int = 32) -> bytes:
    """🇺🇸 `length` bytes derived from `label` — the same label always gives the same bytes.

    🇧🇷 `length` bytes derivados de `label` — o mesmo rótulo sempre dá os mesmos bytes.
    """
    output = b""
    counter = 0
    while len(output) < length:
        output += hashlib.sha256(f"diagnos-contract/{label}/{counter}".encode()).digest()
        counter += 1
    return output[:length]


def b64url(data: bytes) -> str:
    """🇺🇸 RFC 4648 §5 without padding (`docs/PROTOCOL.md §0`). 🇧🇷 RFC 4648 §5 sem padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sdk_keypair() -> HybridKeyPair:
    """🇺🇸 The SDK identity every contract test enrolls with — fixed, so its public keys are fixed too.

    🇧🇷 A identidade do SDK com que todo teste de contrato faz enrollment — fixa, então as públicas também.
    """
    _ek, dk = ML_KEM_768.key_derive(fixed_bytes("sdk/mlkem768-seed", 64))
    return HybridKeyPair.from_secrets(bytearray(fixed_bytes("sdk/x25519")), bytearray(dk))


def seal_to(keypair: HybridKeyPair, plaintext: bytes, aad: str, *, label: str) -> dict[str, str]:
    """🇺🇸 Seals `plaintext` to `keypair` the way the vault/web app does (`docs/PROTOCOL.md §6`), deterministically.

    🇧🇷 Sela `plaintext` para `keypair` do jeito que o cofre/app web faz (`docs/PROTOCOL.md §6`), deterministicamente.
    """
    eph_secret = fixed_bytes(f"{label}/eph")
    eph_public = nb.crypto_scalarmult_base(eph_secret)
    shared_1 = nb.crypto_scalarmult(eph_secret, keypair.x25519_public)
    shared_2, kem_ciphertext = ML_KEM_768._encaps_internal(keypair.mlkem768_public, fixed_bytes(f"{label}/kem"))
    encapsulation = eph_public + kem_ciphertext
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=HYBRID_SEAL_INFO + encapsulation).derive(
        shared_1 + shared_2
    )
    nonce = fixed_bytes(f"{label}/nonce", 12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad.encode("utf-8"))
    return {"salt": b64url(encapsulation), "nonce": b64url(nonce), "ciphertext": b64url(ciphertext)}


def seal_content(key: bytes, plaintext: bytes, info: str, *, label: str) -> dict[str, str]:
    """🇺🇸 `wrapKey`/`encryptContent` (`docs/PROTOCOL.md §7`) with a fixed salt and nonce.

    🇧🇷 `wrapKey`/`encryptContent` (`docs/PROTOCOL.md §7`) com salt e nonce fixos.
    """
    salt = fixed_bytes(f"{label}/salt", 16)
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info.encode("utf-8")).derive(key)
    nonce = fixed_bytes(f"{label}/nonce", 12)
    ciphertext = AESGCM(derived).encrypt(nonce, plaintext, None)
    return {"salt": b64url(salt), "nonce": b64url(nonce), "ciphertext": b64url(ciphertext)}


def random_seed(enc_key: bytes, session_id: str, *, label: str) -> dict[str, str]:
    """🇺🇸 A valid `random_seed` envelope (`docs/PROTOCOL.md §4`) for this session.

    🇧🇷 Um envelope `random_seed` válido (`docs/PROTOCOL.md §4`) para esta sessão.
    """
    nonce = fixed_bytes(f"{label}/nonce", 12)
    body = json.dumps({"seed": b64url(fixed_bytes(f"{label}/seed"))}, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(enc_key).encrypt(nonce, body, session_id.encode("utf-8"))
    return {"nonce": b64url(nonce), "ciphertext": b64url(ciphertext)}
