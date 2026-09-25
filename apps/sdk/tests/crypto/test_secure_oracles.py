"""🇺🇸 Every enclave primitive cross-checked against an implementation it shares no code with.

PyNaCl (libsodium), `cryptography` (OpenSSL) and `kyber-py` play the oracle:
HMAC-SHA512, HKDF-SHA256, AES-256-GCM, the X25519 + ML-KEM-768 hybrid seal in
both directions, and libsodium's secretstream at every chunk-size boundary
including a rekey. A regression in `apps/sdk/native` therefore shows up as a
mismatch against a library this crate has no influence over, not just against
its own fixed output. The normative TypeScript vectors live in
`test_vectors.py`; this file is the *independent* proof.

🇧🇷 Toda primitiva do enclave conferida contra uma implementação com a qual não compartilha código.

PyNaCl (libsodium), `cryptography` (OpenSSL) e `kyber-py` fazem o papel de
oráculo: HMAC-SHA512, HKDF-SHA256, AES-256-GCM, o selo híbrido X25519 +
ML-KEM-768 nas duas direções, e o secretstream do libsodium em toda fronteira
de tamanho de chunk, incluindo um rekey. Uma regressão em `apps/sdk/native`
aparece, portanto, como divergência contra uma biblioteca sobre a qual este
crate não tem influência, não só contra a própria saída fixa. Os vetores
normativos em TypeScript vivem em `test_vectors.py`; este arquivo é a prova
*independente*.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

import nacl.bindings as nb
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from diagnos._secure import (
    SecretStreamPull,
    SecretStreamPush,
    seal_hybrid,
)
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.envelope import EncryptedPayload
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import (
    SecretBox,
    SecureError,
)
from diagnos.errors import CryptoError
from kyber_py.ml_kem import ML_KEM_768

# 🇺🇸 `imgexam-sdk-hybrid-seal-v1` (`docs/PROTOCOL.md §6`) — the HKDF `info` prefix every hybrid seal uses.
# 🇧🇷 `imgexam-sdk-hybrid-seal-v1` (`docs/PROTOCOL.md §6`) — o prefixo de `info` do HKDF que todo selo híbrido usa.
_HYBRID_SEAL_INFO = b"imgexam-sdk-hybrid-seal-v1"

_TAG_MESSAGE = nb.crypto_secretstream_xchacha20poly1305_TAG_MESSAGE
_TAG_REKEY = nb.crypto_secretstream_xchacha20poly1305_TAG_REKEY
_TAG_FINAL = nb.crypto_secretstream_xchacha20poly1305_TAG_FINAL

_STREAM_SIZES = [0, 1, 15, 16, 17, 63, 64, 65, 1000, 1024 * 1024 + 3]


def _b64url(data: bytes) -> str:
    """🇺🇸 Standard b64url, no padding — matches `diagnos.crypto.encoding.b64url_encode`.

    🇧🇷 b64url padrão, sem padding — casa com `diagnos.crypto.encoding.b64url_encode`.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _python_seal(x25519_public: bytes, mlkem768_public: bytes, plaintext: bytes, aad: str) -> EncryptedPayload:
    """🇺🇸 An independent re-implementation of `docs/PROTOCOL.md §6`'s hybrid seal, an oracle for `HybridKeyPair.open*`.

    PyNaCl's raw `crypto_scalarmult` (X25519) and `kyber_py`'s `ML_KEM_768.encaps`
    stand in for the enclave's own X25519-dalek/`ml-kem` crate; `cryptography`'s
    HKDF/AESGCM stand in for the enclave's HKDF-SHA256/AES-256-GCM. None of this
    shares one line of code with `apps/sdk/native/src/hybrid.rs`.

    🇧🇷 Uma reimplementação independente do selo híbrido de `docs/PROTOCOL.md §6`,
    como oráculo para `HybridKeyPair.open*`.

    O `crypto_scalarmult` cru do PyNaCl (X25519) e o `ML_KEM_768.encaps` do
    `kyber_py` fazem o papel do X25519-dalek/crate `ml-kem` do próprio enclave;
    o HKDF/AESGCM do `cryptography` fazem o papel do HKDF-SHA256/AES-256-GCM do
    enclave. Nada disso compartilha uma linha de código com `apps/sdk/native/src/hybrid.rs`.
    """
    eph_secret = os.urandom(32)
    eph_public = nb.crypto_scalarmult_base(eph_secret)
    shared_secret_1 = nb.crypto_scalarmult(eph_secret, x25519_public)
    shared_secret_2, kem_ciphertext = ML_KEM_768.encaps(mlkem768_public)
    encapsulation = eph_public + kem_ciphertext
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HYBRID_SEAL_INFO + encapsulation).derive(
        shared_secret_1 + shared_secret_2
    )
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad.encode("utf-8"))
    return EncryptedPayload(
        salt=b64url_encode(encapsulation), nonce=b64url_encode(nonce), ciphertext=b64url_encode(ciphertext)
    )


# --- Cross-implementation oracles: HMAC, HKDF, AES-GCM ----------------------


def test_hmac_sha512_matches_hmac_module() -> None:
    """🇺🇸 `SecretBox.hmac_sha512` against Python's own `hmac`/`hashlib`.

    🇧🇷 `SecretBox.hmac_sha512` contra o `hmac`/`hashlib` do próprio Python.
    """
    key = os.urandom(32)
    message = b"the message to authenticate"
    tag = SecretBox.from_bytes(bytearray(key)).hmac_sha512(message)
    expected = hmac.new(key, message, hashlib.sha512).digest()
    assert tag == expected


@pytest.mark.parametrize("length", [32, 48])
@pytest.mark.parametrize("with_salt", [True, False])
def test_hkdf_sha256_matches_cryptography(length: int, with_salt: bool) -> None:
    """🇺🇸 `SecretBox.hkdf_sha256` against `cryptography`'s HKDF, with and without salt, two lengths.

    🇧🇷 `SecretBox.hkdf_sha256` contra o HKDF do `cryptography`, com e sem salt, dois tamanhos.
    """
    ikm = os.urandom(32)
    info = b"test-info-string"
    salt = os.urandom(16) if with_salt else None
    okm = SecretBox.from_bytes(bytearray(ikm)).hkdf_sha256(info=info, length=length, salt=salt)
    expected = HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)
    assert bytes(okm.reveal()) == expected


def test_aes_gcm_seal_matches_cryptography_and_cryptography_opens_it() -> None:
    """🇺🇸 `aes_gcm_seal` produces byte-identical output to `AESGCM.encrypt`, and `cryptography` can open it.

    🇧🇷 `aes_gcm_seal` produz saída idêntica byte a byte a `AESGCM.encrypt`, e o `cryptography` consegue abrir.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    plaintext = b"plaintext content"
    aad = b"context"
    sealed = SecretBox.from_bytes(bytearray(key)).aes_gcm_seal(nonce, plaintext, aad)
    expected = AESGCM(key).encrypt(nonce, plaintext, aad)
    assert sealed == expected
    assert AESGCM(key).decrypt(nonce, sealed, aad) == plaintext


def test_aes_gcm_open_opens_what_cryptography_sealed() -> None:
    """🇺🇸 The reverse direction: `cryptography` seals, `aes_gcm_open` opens it.

    🇧🇷 A direção reversa: `cryptography` sela, `aes_gcm_open` abre.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    plaintext = b"plaintext from cryptography"
    aad = b"context"
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    opened = SecretBox.from_bytes(bytearray(key)).aes_gcm_open(nonce, ciphertext, aad)
    assert opened == plaintext


def test_aes_gcm_seal_and_open_without_aad() -> None:
    """🇺🇸 `aad=None` is a valid, matching choice on both sides.

    🇧🇷 `aad=None` é uma escolha válida e compatível dos dois lados.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    plaintext = b"no aad here"
    sealed = SecretBox.from_bytes(bytearray(key)).aes_gcm_seal(nonce, plaintext)
    expected = AESGCM(key).encrypt(nonce, plaintext, None)
    assert sealed == expected
    opened = SecretBox.from_bytes(bytearray(key)).aes_gcm_open(nonce, sealed)
    assert opened == plaintext


def test_aes_gcm_open_wrong_aad_raises_secure_error() -> None:
    """🇺🇸 A ciphertext sealed under one AAD must not open under another.

    🇧🇷 Um ciphertext selado sob um AAD não pode abrir sob outro.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, b"data", b"right-aad")
    with pytest.raises(SecureError):
        SecretBox.from_bytes(bytearray(key)).aes_gcm_open(nonce, ciphertext, b"wrong-aad")


def test_aes_gcm_open_secret_matches_plaintext() -> None:
    """🇺🇸 `aes_gcm_open_secret` opens straight into a box holding the same bytes `AESGCM` would decrypt.

    🇧🇷 `aes_gcm_open_secret` abre direto numa caixa com os mesmos bytes que `AESGCM` decifraria.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    plaintext = os.urandom(32)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    opened = SecretBox.from_bytes(bytearray(key)).aes_gcm_open_secret(nonce, ciphertext)
    assert bytes(opened.reveal()) == plaintext


def test_aes_gcm_seal_secret_matches_sealing_the_same_bytes_directly() -> None:
    """🇺🇸 Sealing a `SecretBox` as plaintext produces the same bytes as sealing its revealed content.

    🇧🇷 Selar um `SecretBox` como texto claro produz os mesmos bytes que selar o conteúdo revelado dele.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    inner = os.urandom(32)
    sealed = SecretBox.from_bytes(bytearray(key)).aes_gcm_seal_secret(nonce, SecretBox.from_bytes(bytearray(inner)))
    expected = AESGCM(key).encrypt(nonce, inner, None)
    assert sealed == expected


def test_aes_gcm_open_json_field_extracts_the_named_field() -> None:
    """🇺🇸 Seals `{"seed": "<b64url>"}` with `AESGCM`, opens the field straight into a box.

    🇧🇷 Sela `{"seed": "<b64url>"}` com `AESGCM`, abre o campo direto numa caixa.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    aad = b"session-id"
    seed = os.urandom(32)
    plaintext = json.dumps({"seed": _b64url(seed)}).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    opened = SecretBox.from_bytes(bytearray(key)).aes_gcm_open_json_field(nonce, ciphertext, aad, "seed")
    assert bytes(opened.reveal()) == seed


def test_aes_gcm_open_json_field_missing_field_raises() -> None:
    """🇺🇸 A well-formed JSON object missing the requested field still fails closed.

    🇧🇷 Um objeto JSON bem formado sem o campo pedido ainda falha fechado.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    aad = b"session-id"
    plaintext = json.dumps({"other": "value"}).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    with pytest.raises(SecureError):
        SecretBox.from_bytes(bytearray(key)).aes_gcm_open_json_field(nonce, ciphertext, aad, "seed")


def test_aes_gcm_open_json_field_non_json_plaintext_raises() -> None:
    """🇺🇸 A ciphertext that decrypts to non-JSON bytes fails closed too.

    🇧🇷 Um ciphertext que decifra para bytes que não são JSON também falha fechado.
    """
    key = os.urandom(32)
    nonce = os.urandom(12)
    aad = b"session-id"
    ciphertext = AESGCM(key).encrypt(nonce, b"not json at all", aad)
    with pytest.raises(SecureError):
        SecretBox.from_bytes(bytearray(key)).aes_gcm_open_json_field(nonce, ciphertext, aad, "seed")


# --- Hybrid: X25519 + ML-KEM-768 --------------------------------------------


def test_hybrid_keypair_public_key_lengths() -> None:
    """🇺🇸 `generate()`'s public keys are 32 bytes (X25519) and 1184 bytes (ML-KEM-768).

    🇧🇷 As públicas de `generate()` são 32 bytes (X25519) e 1184 bytes (ML-KEM-768).
    """
    keypair = HybridKeyPair.generate()
    assert len(keypair.x25519_public) == 32
    assert len(keypair.mlkem768_public) == 1184


def test_python_sealed_hybrid_opens_with_keypair_open() -> None:
    """🇺🇸 A seal built by the Python oracle (`docs/PROTOCOL.md §6`) opens with `keypair.open`.

    🇧🇷 Um selo montado pelo oráculo Python (`docs/PROTOCOL.md §6`) abre com `keypair.open`.
    """
    keypair = HybridKeyPair.generate()
    plaintext = b'{"hello":"world"}'
    payload = _python_seal(keypair.x25519_public, keypair.mlkem768_public, plaintext, aad="enrollment-1")
    assert keypair.open(payload, "enrollment-1") == plaintext


def test_python_sealed_hybrid_opens_with_keypair_open_secret() -> None:
    """🇺🇸 The same oracle seal, opened straight into a `SecretBox` via `open_secret`.

    🇧🇷 O mesmo selo do oráculo, aberto direto num `SecretBox` via `open_secret`.
    """
    keypair = HybridKeyPair.generate()
    secret_plaintext = os.urandom(32)
    payload = _python_seal(keypair.x25519_public, keypair.mlkem768_public, secret_plaintext, aad="enrollment-2")
    opened = keypair.open_secret(payload, "enrollment-2")
    assert bytes(opened.reveal()) == secret_plaintext


def test_python_sealed_session_opens_with_keypair_open_session() -> None:
    """🇺🇸 A `sealed_session` JSON (`docs/PROTOCOL.md §5`), oracle-sealed, opens with `open_session`.

    🇧🇷 Um JSON de `sealed_session` (`docs/PROTOCOL.md §5`), selado pelo oráculo, abre com `open_session`.
    """
    keypair = HybridKeyPair.generate()
    sign_key = os.urandom(32)
    enc_key = os.urandom(32)
    session_json = json.dumps(
        {
            "session_id": "sess_oracle",
            "sign_key": _b64url(sign_key),
            "enc_key": _b64url(enc_key),
            "expires_at": 1_700_000_000,
        }
    ).encode("utf-8")
    payload = _python_seal(keypair.x25519_public, keypair.mlkem768_public, session_json, aad="enrollment-3")
    opened = keypair.open_session(payload, "enrollment-3")
    assert opened.session_id == "sess_oracle"
    assert opened.expires_at == 1_700_000_000
    assert bytes(opened.sign_key.reveal()) == sign_key
    assert bytes(opened.enc_key.reveal()) == enc_key


def test_native_seal_hybrid_opened_by_python_oracle() -> None:
    """🇺🇸 The reverse direction: the enclave's own `seal_hybrid`, opened by the Python oracle.

    Uses `keypair.x25519_secret().reveal()`/`keypair.mlkem768_secret().reveal()`
    directly — the same 2400-byte FIPS 203 expanded decapsulation key the
    protocol fixes everywhere, confirmed here by the `dk[1152:2336] == ek`
    offset PROTOCOL documents.

    🇧🇷 A direção reversa: o próprio `seal_hybrid` do enclave, aberto pelo oráculo Python.

    Usa `keypair.x25519_secret().reveal()`/`keypair.mlkem768_secret().reveal()`
    direto — a mesma chave de decapsulamento expandida da FIPS 203 de 2400
    bytes que o protocolo fixa em todo lugar, confirmada aqui pelo offset
    `dk[1152:2336] == ek` que o PROTOCOL documenta.
    """
    keypair = HybridKeyPair.generate()
    plaintext = b"sealed by the rust enclave itself"
    aad = "enrollment-reverse"
    payload = seal_hybrid(keypair.x25519_public, keypair.mlkem768_public, plaintext, aad.encode("utf-8"))
    encapsulation, nonce, ciphertext = payload

    x25519_secret = bytes(keypair.x25519_secret().reveal())
    mlkem768_secret = bytes(keypair.mlkem768_secret().reveal())
    assert len(mlkem768_secret) == 2400
    assert mlkem768_secret[1152:2336] == keypair.mlkem768_public

    eph_public, kem_ciphertext = encapsulation[:32], encapsulation[32:]
    shared_secret_1 = nb.crypto_scalarmult(x25519_secret, eph_public)
    shared_secret_2 = ML_KEM_768.decaps(mlkem768_secret, kem_ciphertext)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HYBRID_SEAL_INFO + encapsulation).derive(
        shared_secret_1 + shared_secret_2
    )
    opened = AESGCM(key).decrypt(nonce, ciphertext, aad.encode("utf-8"))
    assert opened == plaintext


def test_from_secrets_reproduces_generate_public_keys() -> None:
    """🇺🇸 `from_secrets` recomputes the exact public keys `generate()` produced from the same secrets.

    🇧🇷 `from_secrets` recalcula exatamente as públicas que `generate()` produziu, a partir das mesmas secretas.
    """
    generated = HybridKeyPair.generate()
    rebuilt = HybridKeyPair.from_secrets(generated.x25519_secret(), generated.mlkem768_secret())
    assert rebuilt.x25519_public == generated.x25519_public
    assert rebuilt.mlkem768_public == generated.mlkem768_public


def test_hybrid_open_wrong_aad_raises() -> None:
    """🇺🇸 A seal bound to one `aad` does not open under another, even with the right keys.

    🇧🇷 Um selo amarrado a um `aad` não abre sob outro, mesmo com as chaves certas.
    """
    keypair = HybridKeyPair.generate()
    payload = _python_seal(keypair.x25519_public, keypair.mlkem768_public, b"data", aad="right-enrollment")
    with pytest.raises(CryptoError):
        keypair.open(payload, "wrong-enrollment")


def test_hybrid_open_after_wipe_raises() -> None:
    """🇺🇸 Once `wipe()` has run, every later `open` raises — the secrets are gone.

    🇧🇷 Depois de `wipe()` rodar, todo `open` posterior lança — as secretas se foram.
    """
    keypair = HybridKeyPair.generate()
    payload = _python_seal(keypair.x25519_public, keypair.mlkem768_public, b"data", aad="enrollment-4")
    keypair.zeroize()
    assert keypair.is_wiped is True
    with pytest.raises(SecureError):
        keypair.open(payload, "enrollment-4")


# --- secretstream: cross-checked against PyNaCl -----------------------------


def test_secretstream_push_pulled_by_pynacl_at_every_boundary() -> None:
    """🇺🇸 `SecretStreamPush` output, pulled chunk by chunk by PyNaCl, at every interesting chunk size.

    Alternates `ad=None`/`ad=b"ad"` per chunk; the last chunk is `final=True`,
    which PyNaCl reports back as `TAG_FINAL` (3).

    🇧🇷 Saída de `SecretStreamPush`, puxada pedaço a pedaço pelo PyNaCl, em toda fronteira interessante de chunk.

    Alterna `ad=None`/`ad=b"ad"` por pedaço; o último pedaço é `final=True`,
    que o PyNaCl reporta de volta como `TAG_FINAL` (3).
    """
    key_bytes = os.urandom(32)
    push = SecretStreamPush(SecretBox.from_bytes(bytearray(key_bytes)))

    pull_state = nb.crypto_secretstream_xchacha20poly1305_state()
    nb.crypto_secretstream_xchacha20poly1305_init_pull(pull_state, push.header, key_bytes)

    for index, size in enumerate(_STREAM_SIZES):
        message = os.urandom(size)
        ad = None if index % 2 == 0 else b"ad"
        is_last = index == len(_STREAM_SIZES) - 1
        chunk = push.push(message, final=is_last, ad=ad)
        opened, tag = nb.crypto_secretstream_xchacha20poly1305_pull(pull_state, chunk, ad)
        assert opened == message
        assert tag == (_TAG_FINAL if is_last else _TAG_MESSAGE)
    assert push.is_finished is True


def test_pynacl_push_pulled_by_secretstreampull_with_a_rekey_chunk() -> None:
    """🇺🇸 PyNaCl pushes (including a `TAG_REKEY` chunk mid-stream), `SecretStreamPull` pulls.

    🇧🇷 PyNaCl empurra (incluindo um chunk `TAG_REKEY` no meio do stream), `SecretStreamPull` puxa.
    """
    key_bytes = os.urandom(32)
    push_state = nb.crypto_secretstream_xchacha20poly1305_state()
    header = nb.crypto_secretstream_xchacha20poly1305_init_push(push_state, key_bytes)

    pull = SecretStreamPull(SecretBox.from_bytes(bytearray(key_bytes)), header)

    messages_and_tags = [
        (b"first", _TAG_MESSAGE),
        (b"second", _TAG_MESSAGE),
        (b"rekey-here", _TAG_REKEY),
        (b"after-rekey", _TAG_MESSAGE),
        (b"the last one", _TAG_FINAL),
    ]
    for message, tag in messages_and_tags:
        chunk = nb.crypto_secretstream_xchacha20poly1305_push(push_state, message, None, tag)
        opened, is_final = pull.pull(chunk)
        assert opened == message
        assert is_final == (tag == _TAG_FINAL)
    assert pull.is_finished is True


def test_push_after_final_raises_secure_error() -> None:
    """🇺🇸 A `push` after `final=True` is refused. 🇧🇷 Um `push` depois de `final=True` é recusado."""
    push = SecretStreamPush(SecretBox.random(32))
    push.push(b"last", final=True)
    with pytest.raises(SecureError):
        push.push(b"too late")


def test_pull_after_final_raises_secure_error() -> None:
    """🇺🇸 A `pull` after the final chunk was seen is refused.

    🇧🇷 Um `pull` depois do chunk final ter sido visto é recusado.
    """
    key_bytes = os.urandom(32)
    push_state = nb.crypto_secretstream_xchacha20poly1305_state()
    header = nb.crypto_secretstream_xchacha20poly1305_init_push(push_state, key_bytes)
    final_chunk = nb.crypto_secretstream_xchacha20poly1305_push(push_state, b"bye", None, _TAG_FINAL)
    extra_chunk = nb.crypto_secretstream_xchacha20poly1305_push(push_state, b"unreachable", None, _TAG_MESSAGE)

    pull = SecretStreamPull(SecretBox.from_bytes(bytearray(key_bytes)), header)
    pull.pull(final_chunk)
    with pytest.raises(SecureError):
        pull.pull(extra_chunk)


def test_tampered_chunk_raises_secure_error() -> None:
    """🇺🇸 Flipping one byte of a pushed chunk makes `SecretStreamPull` reject it.

    🇧🇷 Inverter um byte de um chunk empurrado faz `SecretStreamPull` rejeitá-lo.
    """
    key = SecretBox.random(32)
    push = SecretStreamPush(key)
    chunk = bytearray(push.push(b"authenticated content", final=True))
    chunk[-1] ^= 0x01

    pull = SecretStreamPull(key, push.header)
    with pytest.raises(SecureError):
        pull.pull(bytes(chunk))
