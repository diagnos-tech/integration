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
import struct

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


# 🇺🇸 Frozen wire constants (`docs/PROTOCOL.md §8`), repeated here on purpose: the oracle must not import
#    the SDK's own constants, or a wrong label would agree with itself.
# 🇧🇷 Constantes de fio congeladas (`docs/PROTOCOL.md §8`), repetidas aqui de propósito: o oráculo não pode
#    importar as constantes do próprio SDK, senão um rótulo errado concordaria consigo mesmo.
DOCUMENT_DEK_INFO = "imgexam-patient-dek-v1"
INDEX_INFO = {"patients": "imgexam-patient-index-v1", "exams": "imgexam-exam-index-v1"}
VERSION_CONTENT_INFO = "imgexam-document-version-v1"
DRAFT_CONTENT_INFO = "imgexam-document-draft-v1"


def content_key(dek: bytes, key_id: str, security_context: str) -> bytes:
    """🇺🇸 `HKDF-SHA256(dek, salt = utf8(key_id), info = utf8(security_context))` — the per-object key.

    🇧🇷 `HKDF-SHA256(dek, salt = utf8(key_id), info = utf8(security_context))` — a chave por objeto.
    """
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=key_id.encode("utf-8"), info=security_context.encode("utf-8")
    ).derive(dek)


def seal_body(key: bytes, plaintext: bytes, info: str, *, label: str) -> bytes:
    """🇺🇸 A stored object body as the web app writes it: raw `salt(16) ‖ nonce(12) ‖ ciphertext`.

    🇧🇷 O corpo de um objeto guardado como o app web grava: `salt(16) ‖ nonce(12) ‖ ciphertext` cru.
    """
    salt = fixed_bytes(f"{label}/salt", 16)
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info.encode("utf-8")).derive(key)
    nonce = fixed_bytes(f"{label}/nonce", 12)
    return salt + nonce + AESGCM(derived).encrypt(nonce, plaintext, None)


# 🇺🇸 Frozen wire constants of files (`docs/PROTOCOL.md §9`), repeated for the same reason as above.
# 🇧🇷 Constantes de fio congeladas de arquivos (`docs/PROTOCOL.md §9`), repetidas pelo mesmo motivo acima.
NODE_DEK_INFO = "imgexam-node-dek-v1"
NODE_NAME_INFO = "imgexam-node-name-v1"
SSE_C_INFO_SUFFIX = "|sse-c-v1"
STREAM_CHUNK_BYTES = 1024 * 1024

_TAG_MESSAGE = nb.crypto_secretstream_xchacha20poly1305_TAG_MESSAGE
_TAG_FINAL = nb.crypto_secretstream_xchacha20poly1305_TAG_FINAL


def sse_c_headers(dek: bytes, node_id: str, security_context: str) -> dict[str, str]:
    """🇺🇸 The three SSE-C headers `@repo/magic-files` sends: the content key's sister, in standard base64.

    🇧🇷 Os três headers de SSE-C que o `@repo/magic-files` manda: a irmã da chave de conteúdo, em base64 padrão.
    """
    key = content_key(dek, node_id, security_context + SSE_C_INFO_SUFFIX)
    # 🇺🇸 MD5 here is R2's integrity check of the key, not a security primitive.
    # 🇧🇷 O MD5 aqui é a checagem de integridade da chave pelo R2, não uma primitiva de segurança.
    digest = hashlib.md5(key, usedforsecurity=False).digest()
    return {
        "x-amz-server-side-encryption-customer-algorithm": "AES256",
        "x-amz-server-side-encryption-customer-key": base64.b64encode(key).decode("ascii"),
        "x-amz-server-side-encryption-customer-key-md5": base64.b64encode(digest).decode("ascii"),
    }


def seal_stream(key: bytes, plaintext: bytes, chunk: int = STREAM_CHUNK_BYTES) -> bytes:
    """🇺🇸 A file body as the web app writes it: `header(24) ‖ (len_u32_be ‖ frame)*`, the last frame `FINAL`.

    Full chunks go out as plain messages and the tail — empty on an exact
    multiple — as a separate `FINAL` frame. libsodium draws the header
    itself, so this body is not deterministic; it never enters the contract.

    🇧🇷 O corpo de um arquivo como o app web grava: `header(24) ‖ (len_u32_be ‖ frame)*`, o último frame `FINAL`.

    Chunks cheios saem como mensagens comuns e o resto — vazio num múltiplo
    exato — como um frame `FINAL` separado. A libsodium sorteia o header
    sozinha, então este corpo não é determinístico; ele nunca entra no
    contrato.
    """
    state = nb.crypto_secretstream_xchacha20poly1305_state()
    out = bytearray(nb.crypto_secretstream_xchacha20poly1305_init_push(state, key))
    full = len(plaintext) - len(plaintext) % chunk
    for start in range(0, full, chunk):
        frame = nb.crypto_secretstream_xchacha20poly1305_push(state, plaintext[start : start + chunk], tag=_TAG_MESSAGE)
        out += struct.pack(">I", len(frame)) + frame
    frame = nb.crypto_secretstream_xchacha20poly1305_push(state, plaintext[full:], tag=_TAG_FINAL)
    out += struct.pack(">I", len(frame)) + frame
    return bytes(out)


def open_stream(key: bytes, body: bytes) -> bytes:
    """🇺🇸 The inverse of `seal_stream`; fails unless the last frame is `FINAL` and nothing follows it.

    🇧🇷 O inverso de `seal_stream`; falha a menos que o último frame seja `FINAL` e nada venha depois dele.
    """
    header_bytes = nb.crypto_secretstream_xchacha20poly1305_HEADERBYTES
    state = nb.crypto_secretstream_xchacha20poly1305_state()
    nb.crypto_secretstream_xchacha20poly1305_init_pull(state, body[:header_bytes], key)
    offset, plaintext = header_bytes, bytearray()
    while True:
        (length,) = struct.unpack(">I", body[offset : offset + 4])
        message, tag = nb.crypto_secretstream_xchacha20poly1305_pull(state, body[offset + 4 : offset + 4 + length])
        plaintext += message
        offset += 4 + length
        if tag == _TAG_FINAL:
            if offset != len(body):
                raise ValueError("bytes after the FINAL frame")
            return bytes(plaintext)
