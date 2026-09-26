"""🇺🇸 Round-trip and failure-mode tests for the crypto package.

Properties the vectors don't exercise: random salts/nonces, tamper
detection, and stream truncation.

🇧🇷 Testes de ida-e-volta e de modos de falha do pacote de cripto.

Propriedades que os vetores não exercitam: salts/nonces aleatórios,
detecção de adulteração e truncamento de stream.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

import pytest
from diagnos.crypto.content import derive_content_key
from diagnos.crypto.entropy import EntropyMixer
from diagnos.crypto.envelope import EncryptedPayload, decrypt_content, encrypt_content, unwrap_key, wrap_key
from diagnos.crypto.hybrid import HybridKeyPair, open_hybrid, seal_hybrid
from diagnos.crypto.keys import derive_sse_c_key, sse_c_headers
from diagnos.crypto.secretstream import (
    ABYTES,
    CHUNK_SIZE,
    decrypt_bytes,
    decrypt_stream,
    encrypt_bytes,
    encrypt_stream,
    encrypted_size,
)
from diagnos.crypto.secure import SecureError
from diagnos.errors import CryptoError

# --- envelope.py ---


def test_wrap_key_unwrap_key_roundtrip() -> None:
    """🇺🇸 `unwrap_key(wrap_key(...))` returns the original plaintext, born inside a `SecretBox`.

    🇧🇷 `unwrap_key(wrap_key(...))` devolve o texto claro original, nascido dentro de um `SecretBox`.
    """
    wrapping_key = secrets.token_bytes(32)
    plaintext = secrets.token_bytes(32)
    payload = wrap_key(wrapping_key, plaintext, "imgexam-patient-dek-v1")
    unwrapped = unwrap_key(wrapping_key, payload, "imgexam-patient-dek-v1")
    assert bytes(unwrapped.reveal()) == plaintext


def test_encrypt_content_decrypt_content_roundtrip() -> None:
    """🇺🇸 Same as above, for the content-encryption pair. 🇧🇷 O mesmo, para o par de cifragem de conteúdo."""
    dek = secrets.token_bytes(32)
    plaintext = b'{"legal_name":"Joana"}'
    payload = encrypt_content(dek, plaintext, "imgexam-patient-record-v1")
    assert decrypt_content(dek, payload, "imgexam-patient-record-v1") == plaintext


def test_unwrap_key_wrong_key_raises_crypto_error() -> None:
    """🇺🇸 A wrong wrapping key must fail closed, never return garbage.

    🇧🇷 Uma chave de embrulho errada precisa falhar fechado, nunca devolver lixo.
    """
    payload = wrap_key(secrets.token_bytes(32), b"secret", "imgexam-patient-dek-v1")
    with pytest.raises(CryptoError):
        unwrap_key(secrets.token_bytes(32), payload, "imgexam-patient-dek-v1")


def test_unwrap_key_wrong_info_raises_crypto_error() -> None:
    """🇺🇸 `info` is domain separation — the wrong purpose string must not open it.

    🇧🇷 `info` é separação de domínio — a string de propósito errada não pode abrir.
    """
    wrapping_key = secrets.token_bytes(32)
    payload = wrap_key(wrapping_key, b"secret", "imgexam-patient-dek-v1")
    with pytest.raises(CryptoError):
        unwrap_key(wrapping_key, payload, "imgexam-exam-dek-v1")


def test_encrypted_payload_from_dict_requires_all_fields() -> None:
    """🇺🇸 A malformed payload must raise `CryptoError`, not `KeyError`.

    🇧🇷 Um payload malformado precisa lançar `CryptoError`, não `KeyError`.
    """
    with pytest.raises(CryptoError):
        EncryptedPayload.from_dict({"salt": "a", "nonce": "b"})


def test_encrypted_payload_to_dict_from_dict_roundtrip() -> None:
    """🇺🇸 `from_dict(to_dict(x)) == x`. 🇧🇷 `from_dict(to_dict(x)) == x`."""
    payload = EncryptedPayload(salt="s", nonce="n", ciphertext="c")
    assert EncryptedPayload.from_dict(payload.to_dict()) == payload


def test_encrypted_payload_from_dict_rejects_non_string_fields() -> None:
    """🇺🇸 A field present but not a string (a number, a list) is rejected, not silently coerced.

    🇧🇷 Um campo presente mas que não é string (um número, uma lista) é rejeitado, não convertido em silêncio.
    """
    with pytest.raises(CryptoError):
        EncryptedPayload.from_dict({"salt": "a", "nonce": 123, "ciphertext": "c"})


def test_encrypted_payload_decode_rejects_invalid_b64url() -> None:
    """🇺🇸 A field that is a string but not valid b64url fails at `decode()`, not with a bare `binascii.Error`.

    🇧🇷 Um campo que é string mas não é b64url válido falha em `decode()`, não com um `binascii.Error` cru.
    """
    payload = EncryptedPayload(salt="not base64url!!", nonce="n", ciphertext="c")
    with pytest.raises(CryptoError):
        payload.decode()


# --- hybrid.py ---


def test_seal_hybrid_open_hybrid_roundtrip() -> None:
    """🇺🇸 A freshly generated keypair can open what was sealed to its public keys.

    🇧🇷 Um par gerado na hora consegue abrir o que foi selado para as chaves públicas dele.
    """
    keypair = HybridKeyPair.generate()
    plaintext = b'{"session_id":"sess-1"}'
    sealed = seal_hybrid(keypair.x25519_public, keypair.mlkem768_public, plaintext, aad="enrollment-1")
    assert open_hybrid(keypair, sealed, aad="enrollment-1") == plaintext


def test_open_hybrid_wrong_keypair_raises_crypto_error() -> None:
    """🇺🇸 A seal only opens under the keypair it was addressed to. 🇧🇷 Um selo só abre sob o par a que foi endereçado."""
    recipient = HybridKeyPair.generate()
    other = HybridKeyPair.generate()
    sealed = seal_hybrid(recipient.x25519_public, recipient.mlkem768_public, b"data", aad="enrollment-1")
    with pytest.raises(CryptoError):
        open_hybrid(other, sealed, aad="enrollment-1")


def test_from_secrets_reproduces_generate_public_keys() -> None:
    """🇺🇸 `from_secrets` must recompute the exact public keys `generate()` produced.

    Confirms the FIPS 203 offset (`dk[1152:2336] == ek`) holds for keys this
    SDK itself generates, not only for the vector's fixed keypair.

    🇧🇷 `from_secrets` precisa recalcular exatamente as públicas que `generate()` produziu.

    Confirma que o offset da FIPS 203 (`dk[1152:2336] == ek`) vale para
    chaves que o próprio SDK gera, não só para o par fixo do vetor.
    """
    generated = HybridKeyPair.generate()
    rebuilt = HybridKeyPair.from_secrets(generated.x25519_secret(), generated.mlkem768_secret())
    assert rebuilt.x25519_public == generated.x25519_public
    assert rebuilt.mlkem768_public == generated.mlkem768_public


def test_hybrid_keypair_repr_never_contains_secret_material() -> None:
    """🇺🇸 `repr(keypair)` shows a preview of the public key only, never the secrets.

    🇧🇷 `repr(keypair)` mostra só uma prévia da chave pública, nunca as secretas.
    """
    keypair = HybridKeyPair.generate()
    rendered = repr(keypair)
    assert "enclave" in rendered
    assert bytes(keypair.x25519_secret().reveal()).hex() not in rendered
    assert bytes(keypair.mlkem768_secret().reveal()).hex() not in rendered


def test_zeroize_clears_secrets() -> None:
    """🇺🇸 After `zeroize()`, `is_wiped` is true and using either secret raises `SecureError`.

    🇧🇷 Depois de `zeroize()`, `is_wiped` é verdadeiro e usar qualquer secreta lança `SecureError`.
    """
    keypair = HybridKeyPair.generate()
    keypair.zeroize()
    assert keypair.is_wiped is True
    with pytest.raises(SecureError):
        keypair.x25519_secret()
    with pytest.raises(SecureError):
        keypair.mlkem768_secret()


# --- secretstream.py ---

_SMALL_CHUNK = 64


@pytest.mark.parametrize(
    "size",
    [0, 1, _SMALL_CHUNK, _SMALL_CHUNK + 1, _SMALL_CHUNK * 3],
    ids=["empty", "one_byte", "exact_chunk", "chunk_plus_one", "multi_chunk"],
)
def test_secretstream_roundtrip_at_chunk_boundaries(size: int) -> None:
    """🇺🇸 Round-trips at every interesting boundary around `chunk_size`.

    🇧🇷 Ida-e-volta em toda fronteira interessante ao redor de `chunk_size`.
    """
    key = secrets.token_bytes(32)
    plaintext = secrets.token_bytes(size)
    encrypted = b"".join(encrypt_stream(key, [plaintext], chunk_size=_SMALL_CHUNK))
    assert len(encrypted) == encrypted_size(size, chunk_size=_SMALL_CHUNK)
    decrypted = b"".join(decrypt_stream(key, [encrypted]))
    assert decrypted == plaintext


def test_encrypt_bytes_decrypt_bytes_roundtrip() -> None:
    """🇺🇸 The whole-blob convenience wrappers agree with each other.

    🇧🇷 Os atalhos de blob inteiro concordam entre si.
    """
    key = secrets.token_bytes(32)
    plaintext = secrets.token_bytes(10_000)
    encrypted = encrypt_bytes(key, plaintext)
    assert len(encrypted) == encrypted_size(len(plaintext))
    assert decrypt_bytes(key, encrypted) == plaintext


def test_encrypted_size_matches_actual_output_length() -> None:
    """🇺🇸 `encrypted_size` must predict the byte count before a single byte is uploaded.

    🇧🇷 `encrypted_size` precisa prever a contagem de bytes antes de um único byte ser enviado.
    """
    key = secrets.token_bytes(32)
    for size in (0, 1, CHUNK_SIZE, CHUNK_SIZE + 1):
        plaintext = secrets.token_bytes(size)
        encrypted = encrypt_bytes(key, plaintext)
        assert len(encrypted) == encrypted_size(size)


def test_an_exact_multiple_of_the_chunk_ends_with_an_empty_final_frame() -> None:
    """🇺🇸 Like the web app: full chunks are regular frames and `TAG_FINAL` rides an empty last frame.

    🇧🇷 Como no app web: chunks cheios são frames comuns e o `TAG_FINAL` vai num último frame vazio.
    """
    key = secrets.token_bytes(32)
    frames = list(encrypt_stream(key, [secrets.token_bytes(_SMALL_CHUNK * 2)], chunk_size=_SMALL_CHUNK))
    assert len(frames) == 4  # 🇺🇸/🇧🇷 header + 2 full + empty final
    assert len(frames[-1]) == 4 + ABYTES


def test_decrypt_stream_rejects_tampered_byte() -> None:
    """🇺🇸 Flipping one ciphertext byte must fail the AEAD, not silently corrupt the plaintext.

    🇧🇷 Inverter um byte do ciphertext precisa falhar no AEAD, não corromper o texto claro em silêncio.
    """
    key = secrets.token_bytes(32)
    encrypted = bytearray(encrypt_bytes(key, b"conteudo sensivel do exame"))
    encrypted[-1] ^= 0x01  # 🇺🇸 flips a bit inside the final tag · 🇧🇷 inverte um bit dentro da tag final
    with pytest.raises(CryptoError):
        b"".join(decrypt_stream(key, [bytes(encrypted)]))


def test_decrypt_stream_rejects_data_after_final_tag() -> None:
    """🇺🇸 Bytes appended after `TAG_FINAL` must be rejected, not ignored.

    🇧🇷 Bytes anexados depois do `TAG_FINAL` precisam ser rejeitados, não ignorados.
    """
    key = secrets.token_bytes(32)
    encrypted = encrypt_bytes(key, b"conteudo")
    with pytest.raises(CryptoError):
        b"".join(decrypt_stream(key, [encrypted + b"lixo extra"]))


def test_decrypt_stream_rejects_truncated_stream() -> None:
    """🇺🇸 A stream that stops before `TAG_FINAL` looks like a failed upload, not a short file.

    🇧🇷 Um stream que para antes do `TAG_FINAL` parece um upload que falhou, não um arquivo curto.
    """
    key = secrets.token_bytes(32)
    encrypted = encrypt_bytes(key, secrets.token_bytes(200))
    with pytest.raises(CryptoError):
        b"".join(decrypt_stream(key, [encrypted[:-5]]))


# --- keys.py ---


def test_sse_c_key_is_a_sister_of_the_content_key() -> None:
    """🇺🇸 Same DEK, id and context, different `info`: the SSE-C key never equals the content key.

    🇧🇷 Mesma DEK, id e contexto, `info` diferente: a chave de SSE-C nunca é igual à chave de conteúdo.
    """
    dek = secrets.token_bytes(32)
    sister = derive_sse_c_key(dek, "node-1", "ctx")
    assert sister == derive_sse_c_key(dek, "node-1", "ctx")
    assert sister != derive_sse_c_key(dek, "node-2", "ctx")
    assert sister != bytes(derive_content_key(dek, "node-1", "ctx").reveal())


def test_sse_c_headers_shape_and_md5() -> None:
    """🇺🇸 Standard (padded) base64 key and a matching MD5, per PROTOCOL §10.

    🇧🇷 Chave em base64 padrão (com padding) e MD5 correspondente, conforme PROTOCOL §10.
    """
    key = secrets.token_bytes(32)
    headers = sse_c_headers(key)
    assert headers["x-amz-server-side-encryption-customer-algorithm"] == "AES256"
    assert base64.b64decode(headers["x-amz-server-side-encryption-customer-key"]) == key
    expected_md5 = hashlib.md5(key, usedforsecurity=False).digest()
    assert base64.b64decode(headers["x-amz-server-side-encryption-customer-key-md5"]) == expected_md5


# --- entropy.py ---


def test_entropy_mixer_never_repeats() -> None:
    """🇺🇸 Successive calls must not produce the same bytes.

    🇧🇷 Chamadas sucessivas não podem produzir os mesmos bytes.
    """
    mixer = EntropyMixer()
    outputs = {mixer.random(32) for _ in range(50)}
    assert len(outputs) == 50


def test_entropy_mixer_changes_with_seed() -> None:
    """🇺🇸 Mixing in a server seed changes the output stream.

    🇧🇷 Misturar uma semente do servidor muda o fluxo de saída.
    """
    mixer = EntropyMixer()
    before = mixer.random(32)
    mixer.mix(b"server-seed-example")
    after = mixer.random(32)
    assert before != after


def test_entropy_mixer_random_respects_length() -> None:
    """🇺🇸 Arbitrary lengths, including non-multiples of the block size, come back exact.

    🇧🇷 Tamanhos arbitrários, inclusive não múltiplos do tamanho do bloco, voltam exatos.
    """
    mixer = EntropyMixer()
    assert len(mixer.random(1)) == 1
    assert len(mixer.random(100)) == 100
    assert mixer.random(0) == b""


def test_entropy_mixer_random_rejects_a_negative_length() -> None:
    """🇺🇸 A negative `n` is a caller mistake, not a request for `0` bytes.

    🇧🇷 Um `n` negativo é um engano de quem chama, não um pedido de `0` bytes.
    """
    mixer = EntropyMixer()
    with pytest.raises(ValueError, match="n não pode ser negativo"):
        mixer.random(-1)
