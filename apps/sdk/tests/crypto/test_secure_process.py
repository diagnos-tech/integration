"""🇺🇸 The enclave's process-wide guarantees: `fork()` wipes, the lock policy, hardening and the one-time warning.

These tests deliberately leave the current process alone where they can —
`fork()` children and `subprocess`es carry the destructive part (lowering
`RLIMIT_MEMLOCK`, `DIAGNOS_MEMORY_LOCK=require`), so a failure here never
poisons the rest of the suite.

🇧🇷 As garantias do enclave para o processo inteiro: `fork()` apaga, política de travamento, hardening e o aviso único.

Estes testes deixam o processo atual em paz sempre que possível — filhos de
`fork()` e `subprocess`es carregam a parte destrutiva (baixar o
`RLIMIT_MEMLOCK`, `DIAGNOS_MEMORY_LOCK=require`), então uma falha aqui nunca
contamina o resto da suíte.
"""

from __future__ import annotations

import base64
import os
import resource
import subprocess
import sys
import warnings

import nacl.bindings as nb
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.envelope import EncryptedPayload
from diagnos.crypto.secure import (
    MemoryLockWarning,
    SecretBox,
    SecureError,
    harden_process,
    memory_status,
    warn_if_unlocked,
)
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


# --- fork() ------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "linux", reason="MADV_WIPEONFORK is Linux-only")
def test_fork_child_cannot_use_the_parents_box() -> None:
    """🇺🇸 A box allocated in the parent reads as wiped in a `fork()` child; the parent is unaffected.

    Uses `os.fork()` directly (not `multiprocessing`) so the child is a bare
    copy-on-write clone of this exact process, the scenario `MADV_WIPEONFORK`
    defends against. The child reports success (`os._exit(0)`) only if using
    the box raised `SecureError` mentioning "fork"; any other outcome exits
    non-zero, which fails the assertion on `waitpid`'s status.

    🇧🇷 Uma caixa alocada no pai lê como apagada num filho de `fork()`; o pai não é afetado.

    Usa `os.fork()` direto (não `multiprocessing`) para o filho ser um clone
    copy-on-write exato deste processo, o cenário que `MADV_WIPEONFORK`
    defende. O filho reporta sucesso (`os._exit(0)`) só se usar a caixa
    lançou `SecureError` mencionando "fork"; qualquer outro desfecho sai
    diferente de zero, o que falha a asserção no status do `waitpid`.
    """
    box = SecretBox.from_bytes(bytearray(b"\x42" * 32))

    child_pid = os.fork()
    if child_pid == 0:
        try:
            box.reveal()
        except SecureError as exc:
            os._exit(0 if "fork" in str(exc).lower() else 3)
        else:
            os._exit(4)

    _, status = os.waitpid(child_pid, 0)
    assert os.WIFEXITED(status) is True
    assert os.WEXITSTATUS(status) == 0
    assert bytes(box.reveal()) == b"\x42" * 32


# --- Lock policy (DIAGNOS_MEMORY_LOCK) --------------------------------------


_CAP_IPC_LOCK = 14


def _skip_if_memlock_limit_is_bypassed() -> None:
    """🇺🇸 Skips when this process may hold `CAP_IPC_LOCK`, which makes the kernel ignore `RLIMIT_MEMLOCK`.

    The enclave raises `CAP_IPC_LOCK` from *permitted* to *effective* on its
    own (`native/src/locked/caps.rs`), so running as root — a dev container,
    most CI images — means `mlock` never hits the lowered limit and these
    scenarios cannot happen. That is the capability working, not a bug, so the
    test says so instead of failing.

    🇧🇷 Pula quando este processo pode ter `CAP_IPC_LOCK`, que faz o kernel ignorar o `RLIMIT_MEMLOCK`.

    O enclave sobe `CAP_IPC_LOCK` de *permitted* para *effective* sozinho
    (`native/src/locked/caps.rs`), então rodar como root — um dev container, a
    maioria das imagens de CI — significa que o `mlock` nunca bate no limite
    baixado e estes cenários não acontecem. É a capability funcionando, não um
    bug, então o teste diz isso em vez de falhar.
    """
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            permitted = next((line for line in status if line.startswith("CapPrm:")), None)
    except OSError:
        return
    if permitted is not None and int(permitted.split()[1], 16) & (1 << _CAP_IPC_LOCK):
        pytest.skip("CAP_IPC_LOCK is permitted (running as root?): the kernel ignores RLIMIT_MEMLOCK")


def _lower_memlock_or_skip() -> None:
    """🇺🇸 Lowers `RLIMIT_MEMLOCK` to 4096 bytes for this process; skips the test if that is not possible.

    🇧🇷 Baixa o `RLIMIT_MEMLOCK` deste processo para 4096 bytes; pula o teste se não for possível.
    """
    _soft, hard = resource.getrlimit(resource.RLIMIT_MEMLOCK)
    if hard != resource.RLIM_INFINITY and hard < 4096:
        pytest.skip(f"RLIMIT_MEMLOCK hard limit ({hard}) is below 4096; cannot run this scenario")
    try:
        resource.setrlimit(resource.RLIMIT_MEMLOCK, (4096, 4096))
    except (ValueError, OSError) as exc:
        pytest.skip(f"could not lower RLIMIT_MEMLOCK: {exc}")


def test_memory_lock_require_refuses_once_the_limit_is_exhausted() -> None:
    """🇺🇸 `DIAGNOS_MEMORY_LOCK=require`, limit lowered first, eventually raises `SecureError` mentioning `mlock`.

    Runs in a subprocess: the lock policy is read once and cached for the
    life of the process (`locked/mod.rs`'s `OnceLock`), so this cannot be
    exercised in-process alongside every other test here, which all run
    under the default `best-effort` policy.

    🇧🇷 `DIAGNOS_MEMORY_LOCK=require`, com `RLIMIT_MEMLOCK` baixado antes, lança `SecureError` mencionando `mlock`.

    Roda num subprocesso: a política de travamento é lida uma vez e cacheada
    pela vida do processo (`OnceLock` de `locked/mod.rs`), então isto não dá
    para exercitar no mesmo processo dos outros testes daqui, que rodam todos
    sob a política `best-effort` padrão.
    """
    _skip_if_memlock_limit_is_bypassed()
    _soft, hard = resource.getrlimit(resource.RLIMIT_MEMLOCK)
    if hard != resource.RLIM_INFINITY and hard < 4096:
        pytest.skip(f"RLIMIT_MEMLOCK hard limit ({hard}) is below 4096; cannot run this scenario")

    script = (
        "import os, resource, sys\n"
        "resource.setrlimit(resource.RLIMIT_MEMLOCK, (4096, 4096))\n"
        "from diagnos._secure import SecretBox, SecureError\n"
        "try:\n"
        "    boxes = [SecretBox.random(32) for _ in range(100_000)]\n"
        "except SecureError as exc:\n"
        "    sys.exit(0 if 'mlock' in str(exc).lower() else 2)\n"
        "else:\n"
        "    sys.exit(1)\n"
    )
    env = {**os.environ, "DIAGNOS_MEMORY_LOCK": "require"}
    result = subprocess.run([sys.executable, "-c", script], env=env, timeout=60, check=False)  # noqa: S603
    assert result.returncode == 0


def test_memory_lock_best_effort_allows_allocation_past_the_limit() -> None:
    """🇺🇸 Without `DIAGNOS_MEMORY_LOCK=require`, allocating past `RLIMIT_MEMLOCK` still succeeds, best-effort.

    `memory_status()["unlocked_allocations"]` counts at least one refusal
    afterwards — the whole point of `best-effort` is that the SDK keeps
    working and merely notices.

    🇧🇷 Sem `DIAGNOS_MEMORY_LOCK=require`, alocar além do `RLIMIT_MEMLOCK` ainda dá certo, best-effort.

    `memory_status()["unlocked_allocations"]` conta ao menos uma recusa
    depois — o ponto inteiro do `best-effort` é o SDK continuar funcionando e
    só perceber.
    """
    _skip_if_memlock_limit_is_bypassed()
    _soft, hard = resource.getrlimit(resource.RLIMIT_MEMLOCK)
    if hard != resource.RLIM_INFINITY and hard < 4096:
        pytest.skip(f"RLIMIT_MEMLOCK hard limit ({hard}) is below 4096; cannot run this scenario")

    script = (
        "import resource, sys\n"
        "resource.setrlimit(resource.RLIMIT_MEMLOCK, (4096, 4096))\n"
        "from diagnos._secure import SecretBox\n"
        "from diagnos.crypto.secure import memory_status\n"
        "boxes = [SecretBox.random(32) for _ in range(8)]\n"
        "status = memory_status()\n"
        "sys.exit(0 if status['unlocked_allocations'] > 0 else 1)\n"
    )
    result = subprocess.run([sys.executable, "-c", script], timeout=60, check=False)  # noqa: S603
    assert result.returncode == 0


# --- harden_process() / memory_status() -------------------------------------

_HARDEN_PROCESS_KEYS = {
    "platform",
    "core_dumps_disabled",
    "ptrace_restricted",
    "memlock_soft_raised",
    "memlock_soft",
    "memlock_hard",
}

_MEMORY_STATUS_KEYS = {
    "platform",
    "backend",
    "guard_pages",
    "wipe_on_fork",
    "page_size",
    "lock_policy",
    "live_secrets",
    "unlocked_allocations",
    "last_lock_errno",
    "memlock_soft",
    "memlock_hard",
}


def test_harden_process_returns_documented_keys_and_is_idempotent() -> None:
    """🇺🇸 `harden_process()` reports every documented key, and calling it twice is harmless.

    🇧🇷 `harden_process()` reporta toda chave documentada, e chamar duas vezes é inofensivo.
    """
    first = harden_process()
    assert _HARDEN_PROCESS_KEYS <= first.keys()
    second = harden_process()
    assert _HARDEN_PROCESS_KEYS <= second.keys()
    assert second["core_dumps_disabled"] == first["core_dumps_disabled"]
    assert second["ptrace_restricted"] == first["ptrace_restricted"]


def test_memory_status_returns_documented_keys() -> None:
    """🇺🇸 `memory_status()` reports every documented key.

    🇧🇷 `memory_status()` reporta toda chave documentada.
    """
    status = memory_status()
    assert _MEMORY_STATUS_KEYS <= status.keys()


# --- warn_if_unlocked() -------------------------------------------------------


def test_warn_if_unlocked_emits_once_when_unlocked_allocations_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 `warn_if_unlocked()` emits `MemoryLockWarning` exactly once, even across two calls.

    🇧🇷 `warn_if_unlocked()` emite `MemoryLockWarning` exatamente uma vez, mesmo em duas chamadas.
    """
    monkeypatch.setattr("diagnos.crypto.secure._warned_unlocked", False)
    monkeypatch.setattr(
        "diagnos.crypto.secure.memory_status", lambda: {"unlocked_allocations": 1, "last_lock_errno": 12}
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_if_unlocked()
        warn_if_unlocked()
    memory_lock_warnings = [w for w in caught if issubclass(w.category, MemoryLockWarning)]
    assert len(memory_lock_warnings) == 1


def test_warn_if_unlocked_emits_nothing_when_everything_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `warn_if_unlocked()` emits nothing when `unlocked_allocations` is zero.

    🇧🇷 `warn_if_unlocked()` não emite nada quando `unlocked_allocations` é zero.
    """
    monkeypatch.setattr("diagnos.crypto.secure._warned_unlocked", False)
    monkeypatch.setattr("diagnos.crypto.secure.memory_status", lambda: {"unlocked_allocations": 0})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_if_unlocked()
    memory_lock_warnings = [w for w in caught if issubclass(w.category, MemoryLockWarning)]
    assert len(memory_lock_warnings) == 0
