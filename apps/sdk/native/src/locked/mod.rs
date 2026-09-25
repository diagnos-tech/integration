//! 🇺🇸 [`LockedBuffer`]: bytes that live in a page-locked, guard-paged, wipe-on-fork region.
//!
//! The safe API of the enclave. The platform code (`unix.rs`, `windows.rs`)
//! only knows how to map, lock and unmap a region; everything about *meaning*
//! — the sentinel that detects a fork, the explicit wipe, the lock policy —
//! lives here, in safe Rust.
//!
//! Layout of the data region: `[sentinel 8 B][payload]`. The sentinel is a
//! fixed non-zero word written at allocation. On Linux the region is marked
//! `MADV_WIPEONFORK`, so a `fork()` child reads all zeros: the missing
//! sentinel is how a read in the child fails with a clear error instead of
//! silently using an all-zero key.
//!
//! Lock policy (`DIAGNOS_MEMORY_LOCK`): `best-effort` (default) keeps working
//! when `mlock` is refused — the region still has guard pages, `MADV_DONTDUMP`
//! and zero-on-drop, and the refusal is counted so the SDK can warn once;
//! `require` makes the refusal an error, for deployments that would rather
//! not start than run with swappable keys.
//!
//! 🇧🇷 [`LockedBuffer`]: bytes que vivem numa região travada em página, com guard pages e apagada no fork.
//!
//! A API segura do enclave. O código de plataforma (`unix.rs`, `windows.rs`)
//! só sabe mapear, travar e desmapear uma região; tudo sobre *significado* —
//! a sentinela que detecta um fork, o apagar explícito, a política de
//! travamento — vive aqui, em Rust seguro.
//!
//! Layout da região de dados: `[sentinela 8 B][payload]`. A sentinela é uma
//! palavra fixa e não nula escrita na alocação. No Linux a região é marcada
//! `MADV_WIPEONFORK`, então um filho de `fork()` lê só zeros: a sentinela
//! ausente é como uma leitura no filho falha com erro claro em vez de usar em
//! silêncio uma chave toda zero.
//!
//! Política de travamento (`DIAGNOS_MEMORY_LOCK`): `best-effort` (padrão)
//! continua funcionando quando `mlock` é recusado — a região ainda tem guard
//! pages, `MADV_DONTDUMP` e zero-ao-descartar, e a recusa é contada para o
//! SDK avisar uma vez; `require` transforma a recusa em erro, para
//! deployments que preferem não subir a rodar com chaves que podem ir ao swap.

#[cfg(unix)]
mod unix;
#[cfg(unix)]
use unix as platform;

#[cfg(target_os = "linux")]
pub mod caps;

#[cfg(windows)]
mod windows;
#[cfg(windows)]
use windows as platform;

use std::sync::atomic::{AtomicI32, AtomicUsize, Ordering};
use std::sync::OnceLock;

use zeroize::Zeroize;

use crate::error::Error;

const SENTINEL_LEN: usize = 8;
const SENTINEL: u64 = 0x1A5E_C0DE_5EC0_1E55;

static LIVE: AtomicUsize = AtomicUsize::new(0);
static UNLOCKED: AtomicUsize = AtomicUsize::new(0);
static LAST_LOCK_ERRNO: AtomicI32 = AtomicI32::new(0);
static POLICY: OnceLock<LockPolicy> = OnceLock::new();

/// 🇺🇸 What to do when the OS refuses to lock a page. 🇧🇷 O que fazer quando o SO recusa travar uma página.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LockPolicy {
    /// 🇺🇸 Keep going, count the refusal (default). 🇧🇷 Segue em frente, conta a recusa (padrão).
    BestEffort,
    /// 🇺🇸 Fail the allocation. 🇧🇷 Falha a alocação.
    Require,
}

impl LockPolicy {
    /// 🇺🇸 Read once from `DIAGNOS_MEMORY_LOCK`; anything but `require` is best-effort.
    /// 🇧🇷 Lida uma vez de `DIAGNOS_MEMORY_LOCK`; qualquer coisa que não `require` é best-effort.
    pub fn current() -> Self {
        *POLICY.get_or_init(|| match std::env::var("DIAGNOS_MEMORY_LOCK") {
            Ok(value) if value.trim().eq_ignore_ascii_case("require") => Self::Require,
            _ => Self::BestEffort,
        })
    }

    /// 🇺🇸 The name Python reports. 🇧🇷 O nome que o Python reporta.
    #[must_use]
    pub fn name(self) -> &'static str {
        match self {
            Self::BestEffort => "best-effort",
            Self::Require => "require",
        }
    }
}

/// 🇺🇸 Process-wide counters for `memory_status()`. 🇧🇷 Contadores do processo para `memory_status()`.
#[derive(Debug, Clone, Copy)]
pub struct Stats {
    /// 🇺🇸 Buffers currently alive. 🇧🇷 Buffers vivos agora.
    pub live: usize,
    /// 🇺🇸 Allocations that could not be locked since process start. 🇧🇷 Alocações que não puderam ser travadas desde o início do processo.
    pub unlocked: usize,
    /// 🇺🇸 errno of the last `mlock` refusal, 0 if none. 🇧🇷 errno da última recusa de `mlock`, 0 se nenhuma.
    pub last_lock_errno: i32,
    /// 🇺🇸 Page size the regions are rounded to. 🇧🇷 Tamanho de página ao qual as regiões são arredondadas.
    pub page_size: usize,
}

/// 🇺🇸 A snapshot of the counters. 🇧🇷 Um retrato dos contadores.
#[must_use]
pub fn stats() -> Stats {
    Stats {
        live: LIVE.load(Ordering::Relaxed),
        unlocked: UNLOCKED.load(Ordering::Relaxed),
        last_lock_errno: LAST_LOCK_ERRNO.load(Ordering::Relaxed),
        page_size: platform::page_size(),
    }
}

/// 🇺🇸 Owned bytes in a locked region; see the module docs. 🇧🇷 Bytes próprios numa região travada; veja a doc do módulo.
pub struct LockedBuffer {
    region: platform::Region,
    len: usize,
    locked: bool,
    wiped: bool,
}

impl LockedBuffer {
    /// 🇺🇸 A zeroed buffer of `len` bytes (`len > 0`). 🇧🇷 Um buffer zerado de `len` bytes (`len > 0`).
    pub fn new(len: usize) -> Result<Self, Error> {
        if len == 0 {
            return Err(Error::EmptySecret);
        }
        let payload = SENTINEL_LEN.checked_add(len).ok_or(Error::Allocation)?;
        let mut region = platform::Region::map(payload)?;
        let locked = match region.lock() {
            Ok(()) => true,
            Err(errno) => {
                if LockPolicy::current() == LockPolicy::Require {
                    return Err(Error::LockFailed(errno));
                }
                UNLOCKED.fetch_add(1, Ordering::Relaxed);
                LAST_LOCK_ERRNO.store(errno, Ordering::Relaxed);
                false
            }
        };
        region.data_mut()[..SENTINEL_LEN].copy_from_slice(&SENTINEL.to_ne_bytes());
        LIVE.fetch_add(1, Ordering::Relaxed);
        Ok(Self { region, len, locked, wiped: false })
    }

    /// 🇺🇸 A buffer holding a copy of `src`. 🇧🇷 Um buffer com uma cópia de `src`.
    pub fn from_slice(src: &[u8]) -> Result<Self, Error> {
        let mut buffer = Self::new(src.len())?;
        buffer.with_bytes_mut(|data| data.copy_from_slice(src))?;
        Ok(buffer)
    }

    /// 🇺🇸 Payload length in bytes. 🇧🇷 Tamanho do payload em bytes.
    #[must_use]
    pub fn len(&self) -> usize {
        self.len
    }

    /// 🇺🇸 Always `false`: empty buffers cannot be constructed. 🇧🇷 Sempre `false`: buffers vazios não podem ser construídos.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        false
    }

    /// 🇺🇸 Whether `mlock` succeeded for this region. 🇧🇷 Se `mlock` deu certo para esta região.
    #[must_use]
    pub fn is_locked(&self) -> bool {
        self.locked
    }

    /// 🇺🇸 Whether `wipe()` was called. 🇧🇷 Se `wipe()` foi chamado.
    #[must_use]
    pub fn is_wiped(&self) -> bool {
        self.wiped
    }

    fn check(&self) -> Result<(), Error> {
        if self.wiped {
            return Err(Error::Wiped);
        }
        let mut sentinel = [0u8; SENTINEL_LEN];
        sentinel.copy_from_slice(&self.region.data()[..SENTINEL_LEN]);
        if u64::from_ne_bytes(sentinel) == SENTINEL {
            Ok(())
        } else {
            Err(Error::WipedByFork)
        }
    }

    /// 🇺🇸 Runs `f` over the payload; fails if wiped (explicitly or by fork). 🇧🇷 Roda `f` sobre o payload; falha se apagado (explicitamente ou por fork).
    pub fn with_bytes<T>(&self, f: impl FnOnce(&[u8]) -> T) -> Result<T, Error> {
        self.check()?;
        let end = SENTINEL_LEN + self.len;
        Ok(f(&self.region.data()[SENTINEL_LEN..end]))
    }

    /// 🇺🇸 Mutable twin of `with_bytes`. 🇧🇷 Gêmeo mutável de `with_bytes`.
    pub fn with_bytes_mut<T>(&mut self, f: impl FnOnce(&mut [u8]) -> T) -> Result<T, Error> {
        self.check()?;
        let end = SENTINEL_LEN + self.len;
        Ok(f(&mut self.region.data_mut()[SENTINEL_LEN..end]))
    }

    /// 🇺🇸 A new buffer with the same payload. 🇧🇷 Um buffer novo com o mesmo payload.
    pub fn duplicate(&self) -> Result<Self, Error> {
        self.with_bytes(Self::from_slice)?
    }

    /// 🇺🇸 Zeroes the whole region now; every later read fails with `Wiped`. 🇧🇷 Zera a região inteira agora; toda leitura depois falha com `Wiped`.
    pub fn wipe(&mut self) {
        self.region.data_mut().zeroize();
        self.wiped = true;
    }
}

impl Drop for LockedBuffer {
    fn drop(&mut self) {
        self.region.data_mut().zeroize();
        if self.locked {
            self.region.unlock();
        }
        LIVE.fetch_sub(1, Ordering::Relaxed);
    }
}

// 🇺🇸 The region is owned exclusively and only reachable through `&mut self`
//    (or a `Mutex` in the Python classes), so moving it between threads is sound.
// 🇧🇷 A região tem dono exclusivo e só é alcançável por `&mut self` (ou por um
//    `Mutex` nas classes Python), então movê-la entre threads é correto.
#[allow(unsafe_code)]
unsafe impl Send for LockedBuffer {}
#[allow(unsafe_code)]
unsafe impl Sync for LockedBuffer {}
