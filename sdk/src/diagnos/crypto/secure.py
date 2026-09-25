"""🇺🇸 The bridge to `diagnos._secure`, the Rust memory enclave every secret in this SDK lives in.

A `SecretBox` is bytes in page-locked memory (`mlock`), fenced by guard
pages, excluded from core dumps, wiped in a `fork()` child and zeroed the
moment the box is dropped. It never comes back as `bytes`: HMAC, HKDF,
AES-GCM, the hybrid seal and the secretstream all run inside the enclave,
against the locked page. The single exit is `SecretBox.reveal()`, reserved
for the OpenBao export (`session/unseal.py`), and every caller of it zeroes
the `bytearray` it gets. `sdk/native/README.md` has the threat model.

🇧🇷 A ponte para `diagnos._secure`, o enclave de memória em Rust em que todo segredo deste SDK mora.

Um `SecretBox` são bytes em memória travada em página (`mlock`), cercados
por guard pages, excluídos de core dumps, apagados num filho de `fork()` e
zerados no instante em que a caixa é descartada. Ele nunca volta como
`bytes`: HMAC, HKDF, AES-GCM, o selo híbrido e o secretstream rodam dentro
do enclave, contra a página travada. A única saída é `SecretBox.reveal()`,
reservada à exportação para o OpenBao (`session/unseal.py`), e todo
chamador dela zera o `bytearray` que recebe. `sdk/native/README.md` tem o
modelo de ameaça.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

from diagnos import _secure

from .encoding import b64url_decode

SecretBox = _secure.SecretBox
SecureError = _secure.SecureError

# 🇺🇸 What a key parameter accepts: a box, or bytes-like material that will be
#    moved into one (a writable source is zeroed by the move).
# 🇧🇷 O que um parâmetro de chave aceita: uma caixa, ou material tipo bytes que
#    será movido para uma (uma origem gravável é zerada pelo movimento).
SecretLike = SecretBox | bytes | bytearray | memoryview

logger = logging.getLogger("diagnos")
_warned_unlocked = False


class MemoryLockWarning(RuntimeWarning):
    """🇺🇸 Emitted once when the OS refused to lock at least one secret in RAM.

    The secret still has guard pages, no-dump and zero-on-drop; what it lost
    is the guarantee of never reaching swap. The fix is operational, not in
    code: raise `ulimit -l`, grant `CAP_IPC_LOCK`, or set
    `DIAGNOS_MEMORY_LOCK=require` to refuse to run this way.

    🇧🇷 Emitido uma vez quando o SO recusou travar pelo menos um segredo na RAM.

    O segredo ainda tem guard pages, sem dump e zero-ao-descartar; o que
    perdeu foi a garantia de nunca ir ao swap. A correção é operacional, não
    de código: aumente `ulimit -l`, conceda `CAP_IPC_LOCK`, ou defina
    `DIAGNOS_MEMORY_LOCK=require` para se recusar a rodar assim.
    """


def as_secret(value: SecretLike) -> SecretBox:
    """🇺🇸 A `SecretBox` for `value`: the box itself, or a fresh one holding a copy of the bytes.

    Copying `bytes` in cannot erase the caller's original — `bytes` is
    immutable — so the only paths that pass `bytes` here are test vectors
    and the OpenBao restore, both documented as such. Writable sources
    (`bytearray`, writable `memoryview`) are zeroed by the move.

    🇧🇷 Um `SecretBox` para `value`: a própria caixa, ou uma nova com uma cópia dos bytes.

    Copiar `bytes` para dentro não consegue apagar o original de quem
    chamou — `bytes` é imutável — então os únicos caminhos que passam
    `bytes` aqui são vetores de teste e o restore do OpenBao, os dois
    documentados como tais. Origens graváveis (`bytearray`, `memoryview`
    gravável) são zeradas pelo movimento.
    """
    if isinstance(value, SecretBox):
        return value
    return SecretBox.from_bytes(value)


def secret_from_b64url(text: str) -> SecretBox:
    """🇺🇸 Decodes base64url straight into a box.

    `base64` returns immutable `bytes`, so one transient clear copy exists
    on the Python heap until the collector frees it — the reason this helper
    is used only on the OpenBao restore path, never for material the vault
    sends (that is opened inside the enclave, see `transport/seed.py`).

    🇧🇷 Decodifica base64url direto para uma caixa.

    `base64` devolve `bytes` imutável, então uma cópia transitória em claro
    existe no heap do Python até o coletor liberá-la — o motivo de este
    auxiliar ser usado só no caminho de restore do OpenBao, nunca para
    material que o cofre envia (esse é aberto dentro do enclave, veja
    `transport/seed.py`).
    """
    return SecretBox.from_bytes(bytearray(b64url_decode(text)))


def zero(buffer: bytearray) -> None:
    """🇺🇸 Overwrites a `bytearray` (typically from `reveal()`) with zeros, in place.

    🇧🇷 Sobrescreve um `bytearray` (tipicamente de `reveal()`) com zeros, no lugar.
    """
    buffer[:] = bytes(len(buffer))


def memory_status() -> dict[str, Any]:
    """🇺🇸 What the enclave guarantees right now (lock policy, unlocked allocations, limits).

    🇧🇷 O que o enclave garante agora (política de travamento, alocações sem trava, limites).
    """
    return dict(_secure.memory_status())


def harden_process() -> dict[str, Any]:
    """🇺🇸 Disables core dumps and `ptrace` attach for this process and raises the memlock soft limit; idempotent.

    🇧🇷 Desliga core dumps e o attach de `ptrace` neste processo e sobe o limite soft de memlock; idempotente.
    """
    return dict(_secure.harden_process())


def warn_if_unlocked() -> None:
    """🇺🇸 Emits `MemoryLockWarning` (once per process) if any secret could not be locked.

    Called right after a session is unlocked — the moment the process holds
    every secret it will ever hold — so the warning reflects the real
    footprint, not an early, optimistic zero.

    🇧🇷 Emite `MemoryLockWarning` (uma vez por processo) se algum segredo não pôde ser travado.

    Chamado logo depois de uma sessão ser desbloqueada — o momento em que o
    processo segura todo segredo que vai segurar — para o aviso refletir o
    tamanho real, não um zero otimista de início.
    """
    global _warned_unlocked  # noqa: PLW0603 — one warning per process is the whole point
    status = memory_status()
    if _warned_unlocked or int(status.get("unlocked_allocations", 0)) == 0:
        return
    _warned_unlocked = True
    warnings.warn(
        "🇺🇸 diagnos could not lock every secret in RAM (mlock refused, errno "
        f"{status.get('last_lock_errno')}); keys may reach swap. Raise `ulimit -l`, grant CAP_IPC_LOCK, "
        "or set DIAGNOS_MEMORY_LOCK=require to refuse to run this way. "
        "🇧🇷 o diagnos não conseguiu travar todo segredo na RAM (mlock recusado, errno "
        f"{status.get('last_lock_errno')}); chaves podem ir ao swap. Aumente `ulimit -l`, conceda "
        "CAP_IPC_LOCK, ou defina DIAGNOS_MEMORY_LOCK=require para se recusar a rodar assim.",
        MemoryLockWarning,
        stacklevel=2,
    )
    logger.warning("secure memory: %s", status)
