//! 🇺🇸 Unix regions: anonymous `mmap`, guard pages, `mlock`, `madvise` — raw syscalls behind a safe `Region`.
//!
//! A region is `[guard][data pages][guard]`. The guards are `PROT_NONE`: any
//! code in the process that runs off the end of a neighbouring allocation
//! into a secret faults instead of reading it. The data pages are `mlock`ed
//! (never swapped), `MADV_DONTDUMP` (never in a core dump) and, on Linux,
//! `MADV_WIPEONFORK` (zeroed in a `fork()` child). Failures of the advisory
//! calls are ignored on purpose — an old kernel without `WIPEONFORK` should
//! still get every other protection — while an `mlock` failure is reported
//! to the caller, who decides by policy.
//!
//! 🇧🇷 Regiões Unix: `mmap` anônimo, guard pages, `mlock`, `madvise` — syscalls cruas atrás de uma `Region` segura.
//!
//! Uma região é `[guarda][páginas de dados][guarda]`. As guardas são
//! `PROT_NONE`: qualquer código do processo que corra além do fim de uma
//! alocação vizinha para dentro de um segredo falha em vez de lê-lo. As
//! páginas de dados são `mlock`adas (nunca vão ao swap), `MADV_DONTDUMP`
//! (nunca num core dump) e, no Linux, `MADV_WIPEONFORK` (zeradas num filho de
//! `fork()`). Falhas das chamadas consultivas são ignoradas de propósito — um
//! kernel antigo sem `WIPEONFORK` ainda deve receber toda outra proteção —
//! enquanto uma falha de `mlock` é reportada a quem chama, que decide por
//! política.

#![allow(unsafe_code)]

use std::ptr::NonNull;
use std::sync::OnceLock;

use crate::error::Error;

/// 🇺🇸 The system page size, queried once. 🇧🇷 O tamanho de página do sistema, consultado uma vez.
pub fn page_size() -> usize {
    static PAGE: OnceLock<usize> = OnceLock::new();
    *PAGE.get_or_init(|| {
        // SAFETY: sysconf has no preconditions.
        let value = unsafe { libc::sysconf(libc::_SC_PAGESIZE) };
        usize::try_from(value).ok().filter(|size| *size >= 512).unwrap_or(4096)
    })
}

/// 🇺🇸 A mapped `[guard][data][guard]` region. 🇧🇷 Uma região mapeada `[guarda][dados][guarda]`.
pub struct Region {
    base: NonNull<u8>,
    total: usize,
    data: NonNull<u8>,
    data_len: usize,
}

impl Region {
    /// 🇺🇸 Maps a zeroed region able to hold `payload` bytes. 🇧🇷 Mapeia uma região zerada capaz de guardar `payload` bytes.
    pub fn map(payload: usize) -> Result<Self, Error> {
        let page = page_size();
        let data_len = payload.checked_add(page - 1).ok_or(Error::Allocation)? / page * page;
        let total = data_len.checked_add(page.checked_mul(2).ok_or(Error::Allocation)?).ok_or(Error::Allocation)?;

        // SAFETY: anonymous private mapping with no file, no fixed address, no
        // aliasing; the kernel returns MAP_FAILED on error, checked below.
        let base = unsafe {
            libc::mmap(
                std::ptr::null_mut(),
                total,
                libc::PROT_READ | libc::PROT_WRITE,
                libc::MAP_PRIVATE | libc::MAP_ANONYMOUS,
                -1,
                0,
            )
        };
        if base == libc::MAP_FAILED {
            return Err(Error::Allocation);
        }
        let base = NonNull::new(base.cast::<u8>()).ok_or(Error::Allocation)?;

        // SAFETY: both guard pages lie inside the mapping just created; the
        // data pointer is `page` bytes past `base`, within `total`.
        let data = unsafe {
            let ok_low = libc::mprotect(base.as_ptr().cast(), page, libc::PROT_NONE) == 0;
            let high = base.as_ptr().add(page + data_len);
            let ok_high = libc::mprotect(high.cast(), page, libc::PROT_NONE) == 0;
            if !ok_low || !ok_high {
                libc::munmap(base.as_ptr().cast(), total);
                return Err(Error::Allocation);
            }
            NonNull::new_unchecked(base.as_ptr().add(page))
        };
        Ok(Self { base, total, data, data_len })
    }

    /// 🇺🇸 The data pages (zeroed by the kernel at map time). 🇧🇷 As páginas de dados (zeradas pelo kernel no mapeamento).
    pub fn data(&self) -> &[u8] {
        // SAFETY: `data` points at `data_len` readable, writable bytes owned by `self`.
        unsafe { std::slice::from_raw_parts(self.data.as_ptr(), self.data_len) }
    }

    /// 🇺🇸 Mutable view of the data pages. 🇧🇷 Visão mutável das páginas de dados.
    pub fn data_mut(&mut self) -> &mut [u8] {
        // SAFETY: as in `data`, and `&mut self` guarantees exclusivity.
        unsafe { std::slice::from_raw_parts_mut(self.data.as_ptr(), self.data_len) }
    }

    /// 🇺🇸 Pins the data pages in RAM and hides them from dumps/forks; `Err(errno)` if `mlock` refused.
    /// 🇧🇷 Prende as páginas de dados na RAM e as esconde de dumps/forks; `Err(errno)` se `mlock` recusou.
    pub fn lock(&mut self) -> Result<(), i32> {
        // 🇺🇸 The image carries `cap_ipc_lock=+p`; make it effective for this
        //    thread before `mlock` so a granted capability actually counts.
        // 🇧🇷 A imagem carrega `cap_ipc_lock=+p`; torna-a efetiva para esta
        //    thread antes do `mlock` para uma capability concedida contar.
        #[cfg(target_os = "linux")]
        super::caps::ensure_ipc_lock_effective();
        let ptr = self.data.as_ptr().cast::<libc::c_void>();
        // SAFETY: the range is exactly the data pages of this mapping.
        unsafe {
            #[cfg(target_os = "linux")]
            {
                libc::madvise(ptr, self.data_len, libc::MADV_DONTDUMP);
                libc::madvise(ptr, self.data_len, libc::MADV_WIPEONFORK);
            }
            #[cfg(any(target_os = "freebsd", target_os = "dragonfly"))]
            {
                libc::madvise(ptr, self.data_len, libc::MADV_NOCORE);
            }
            if libc::mlock(ptr, self.data_len) == 0 {
                Ok(())
            } else {
                Err(*libc::__errno_location())
            }
        }
    }

    /// 🇺🇸 Releases the pin; the caller has already zeroed the pages. 🇧🇷 Solta a trava; quem chama já zerou as páginas.
    pub fn unlock(&mut self) {
        // SAFETY: the range is exactly the data pages of this mapping.
        unsafe {
            libc::munlock(self.data.as_ptr().cast(), self.data_len);
        }
    }
}

impl Drop for Region {
    fn drop(&mut self) {
        // SAFETY: `base`/`total` describe the mapping created in `map`, unmapped exactly once.
        unsafe {
            libc::munmap(self.base.as_ptr().cast(), self.total);
        }
    }
}
