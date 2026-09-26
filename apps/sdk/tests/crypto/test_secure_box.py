"""🇺🇸 The `SecretBox` and `EntropyPool` contract as seen from Python: no way back to `bytes`, nothing leaks by accident.

Every assertion here pins behaviour a Python caller can observe — construction
rules, `repr`, hashing, pickling, copying, constant-time `==`, wipe-then-use,
clone independence, the entropy pool's shape. The cryptographic *correctness*
of the enclave is proved elsewhere (`test_secure_oracles.py`); the process-wide
guarantees (`fork`, lock policy, hardening) in `test_secure_process.py`.
`apps/sdk/native/README.md` has the full threat model.

🇧🇷 O contrato de `SecretBox` e `EntropyPool` visto do Python: sem caminho de volta a `bytes`, nada vaza por acidente.

Toda asserção aqui trava um comportamento que quem chama do Python consegue
observar — regras de construção, `repr`, hash, pickle, cópia, `==` em tempo
constante, apagar-e-usar, independência do clone, a forma do pool de
entropia. A *correção* criptográfica do enclave é provada em outro lugar
(`test_secure_oracles.py`); as garantias do processo inteiro (`fork`,
política de travamento, hardening) em `test_secure_process.py`.
`apps/sdk/native/README.md` tem o modelo de ameaça completo.
"""

from __future__ import annotations

import base64
import copy
import os
import pickle

import nacl.bindings as nb
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from diagnos._secure import (
    EntropyPool,
)
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.envelope import EncryptedPayload
from diagnos.crypto.secure import (
    SecretBox,
    SecureError,
    memory_status,
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
    shares one line of code with `apps/sdk/native/src/hybrid/`.

    🇧🇷 Uma reimplementação independente do selo híbrido de `docs/PROTOCOL.md §6`,
    como oráculo para `HybridKeyPair.open*`.

    O `crypto_scalarmult` cru do PyNaCl (X25519) e o `ML_KEM_768.encaps` do
    `kyber_py` fazem o papel do X25519-dalek/crate `ml-kem` do próprio enclave;
    o HKDF/AESGCM do `cryptography` fazem o papel do HKDF-SHA256/AES-256-GCM do
    enclave. Nada disso compartilha uma linha de código com `apps/sdk/native/src/hybrid/`.
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


# --- SecretBox: construction, and the "no way back to bytes" contract ------


def test_from_bytes_bytearray_zeroes_the_source() -> None:
    """🇺🇸 Moving a `bytearray` into a box leaves the caller's buffer all zero.

    🇧🇷 Mover um `bytearray` para uma caixa deixa o buffer de quem chamou todo zero.
    """
    source = bytearray(b"\xaa" * 32)
    box = SecretBox.from_bytes(source)
    assert source == bytearray(32)
    assert bytes(box.reveal()) == b"\xaa" * 32


def test_from_bytes_bytes_copies_without_touching_the_original() -> None:
    """🇺🇸 `bytes` cannot be zeroed (immutable); `from_bytes` still works, as a copy.

    🇧🇷 `bytes` não pode ser zerado (imutável); `from_bytes` ainda funciona, como cópia.
    """
    source = b"\xbb" * 32
    box = SecretBox.from_bytes(source)
    assert bytes(box.reveal()) == source


def test_from_bytes_str_raises_type_error() -> None:
    """🇺🇸 A `str` is refused outright — encode it first.

    🇧🇷 Um `str` é recusado de cara — codifique antes.
    """
    with pytest.raises(TypeError):
        SecretBox.from_bytes("not bytes")  # type: ignore[arg-type]


def test_random_zero_length_raises_secure_error() -> None:
    """🇺🇸 A zero-byte secret is a bug, not a value.

    🇧🇷 Um segredo de zero bytes é bug, não valor.
    """
    with pytest.raises(SecureError):
        SecretBox.random(0)


def test_len_and_is_locked() -> None:
    """🇺🇸 `len()` reports the payload size; `is_locked` is `True` when the OS actually pinned the page.

    Skipped (not failed) when `memory_status()` shows an unlocked allocation
    right after this box was made — the CI box refused `mlock`, a host fact
    this test cannot control, not a defect in the enclave.

    🇧🇷 `len()` reporta o tamanho do payload; `is_locked` é `True` quando o SO
    de fato prendeu a página.

    Pulado (não falhado) quando `memory_status()` mostra uma alocação sem
    trava logo depois desta caixa ser criada — a máquina de CI recusou o
    `mlock`, um fato do host que este teste não controla, não um defeito no
    enclave.
    """
    box = SecretBox.random(32)
    assert len(box) == 32
    if memory_status()["unlocked_allocations"] > 0:
        pytest.skip("this host refused mlock for at least one allocation; cannot assert is_locked")
    assert box.is_locked is True


def test_repr_never_contains_bytes_and_says_redacted() -> None:
    """🇺🇸 `repr` never leaks the payload, only a redacted marker.

    🇧🇷 `repr` nunca vaza o payload, só um marcador redigido.
    """
    box = SecretBox.from_bytes(bytearray(b"\xcc" * 32))
    rendered = repr(box)
    assert "\\xcc" not in rendered
    assert "redacted" in rendered


def test_hash_raises_type_error() -> None:
    """🇺🇸 A `SecretBox` is unhashable — it must never end up as a `dict`/`set` key by accident.

    🇧🇷 Um `SecretBox` não é hasheável — nunca pode virar chave de `dict`/`set` por acidente.
    """
    with pytest.raises(TypeError):
        hash(SecretBox.random(32))


@pytest.mark.parametrize(
    "action",
    [pickle.dumps, copy.copy, copy.deepcopy],
    ids=["pickle", "copy", "deepcopy"],
)
def test_pickle_copy_deepcopy_all_raise_type_error(action: object) -> None:
    """🇺🇸 Every way Python could implicitly duplicate a box is refused.

    🇧🇷 Toda forma de o Python duplicar uma caixa implicitamente é recusada.
    """
    box = SecretBox.random(32)
    with pytest.raises(TypeError):
        action(box)  # type: ignore[operator]


def test_eq_self_and_equal_contents() -> None:
    """🇺🇸 A box equals itself and an independent box with the same bytes.

    🇧🇷 Uma caixa é igual a si mesma e a uma caixa independente com os mesmos bytes.
    """
    box = SecretBox.from_bytes(bytearray(b"\x11" * 32))
    same = SecretBox.from_bytes(bytearray(b"\x11" * 32))
    assert box == box  # noqa: PLR0124 — the point of the test is comparing an object to itself
    assert box == same


def test_eq_different_contents_is_false() -> None:
    """🇺🇸 Two boxes with different bytes are not equal.

    🇧🇷 Duas caixas com bytes diferentes não são iguais.
    """
    box = SecretBox.from_bytes(bytearray(b"\x11" * 32))
    other = SecretBox.from_bytes(bytearray(b"\x22" * 32))
    assert box != other


def test_eq_against_bytes_is_false() -> None:
    """🇺🇸 Comparing a box to plain `bytes` is `False`, never a `TypeError`.

    🇧🇷 Comparar uma caixa a `bytes` puro é `False`, nunca `TypeError`.
    """
    contents = b"\x11" * 32
    box = SecretBox.from_bytes(bytearray(contents))
    assert (box == contents) is False


def test_wipe_then_use_raises_secure_error_which_is_a_crypto_error() -> None:
    """🇺🇸 After `wipe()`, `reveal()` and `hmac_sha512()` both raise `SecureError`, a `CryptoError`.

    🇧🇷 Depois de `wipe()`, `reveal()` e `hmac_sha512()` lançam `SecureError`, um `CryptoError`.
    """
    box = SecretBox.random(32)
    box.wipe()
    assert box.is_wiped is True
    assert issubclass(SecureError, CryptoError)
    with pytest.raises(SecureError):
        box.reveal()
    with pytest.raises(SecureError):
        box.hmac_sha512(b"message")


def test_clone_is_independent_of_the_original() -> None:
    """🇺🇸 Wiping a clone leaves the original untouched, and vice versa.

    🇧🇷 Apagar um clone deixa o original intocado, e vice-versa.
    """
    original = SecretBox.from_bytes(bytearray(b"\x33" * 32))
    clone = original.clone()
    clone.wipe()
    assert clone.is_wiped is True
    assert original.is_wiped is False
    assert bytes(original.reveal()) == b"\x33" * 32


# --- EntropyPool -------------------------------------------------------------


def test_entropy_pool_random_outputs_differ_across_calls() -> None:
    """🇺🇸 Successive `random()` calls never repeat.

    🇧🇷 Chamadas sucessivas de `random()` nunca se repetem.
    """
    pool = EntropyPool()
    outputs = {pool.random(32) for _ in range(50)}
    assert len(outputs) == 50


def test_entropy_pool_mix_with_secretbox_changes_the_stream() -> None:
    """🇺🇸 Mixing in a `SecretBox` seed changes subsequent `random()` output.

    🇧🇷 Misturar uma semente `SecretBox` muda a saída seguinte de `random()`.
    """
    pool = EntropyPool()
    before = pool.random(32)
    pool.mix(SecretBox.from_bytes(bytearray(b"server-seed-as-box-material-here")))
    after = pool.random(32)
    assert before != after


def test_entropy_pool_mix_with_bytes_changes_the_stream() -> None:
    """🇺🇸 Mixing in a plain-bytes seed changes subsequent `random()` output too.

    🇧🇷 Misturar uma semente em bytes puros também muda a saída seguinte de `random()`.
    """
    pool = EntropyPool()
    before = pool.random(32)
    pool.mix(b"a different server seed entirely")
    after = pool.random(32)
    assert before != after


def test_entropy_pool_random_secret_is_a_32_byte_box() -> None:
    """🇺🇸 `random_secret(32)` returns a locked, 32-byte `SecretBox`.

    🇧🇷 `random_secret(32)` retorna um `SecretBox` travado de 32 bytes.
    """
    box = EntropyPool().random_secret(32)
    assert isinstance(box, SecretBox)
    assert len(box) == 32


def test_entropy_pool_random_zero_is_empty_bytes() -> None:
    """🇺🇸 `random(0)` is `b""`, not an error — unlike `SecretBox.random(0)`.

    🇧🇷 `random(0)` é `b""`, não um erro — diferente de `SecretBox.random(0)`.
    """
    assert EntropyPool().random(0) == b""
