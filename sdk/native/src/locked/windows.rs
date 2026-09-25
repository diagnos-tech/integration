//! 🇺🇸 Windows regions: a page-aligned heap allocation pinned with `VirtualLock`.
//!
//! Windows has no `fork()` and no core-dump advisory, so the two protections
//! this backend offers are the two that exist: `VirtualLock` (no paging to
//! disk) and zero-on-drop. Guard pages are not implemented here — the SDK's
//! production target is Linux; this backend keeps the CLI usable on a
//! developer's Windows machine with honest, reduced guarantees that
//! `memory_status()` reports as such.
//!
//! 🇧🇷 Regiões Windows: uma alocação de heap alinhada a página, presa com `VirtualLock`.
//!
//! Windows não tem `fork()` nem aviso de core dump, então as duas proteções
//! que este backend oferece são as duas que existem: `VirtualLock` (sem
//! paginação para disco) e zero-ao-descartar. Guard pages não são
//! implementadas aqui — o alvo de produção do SDK é Linux; este backend
//! mantém a CLI utilizável na máquina Windows de quem desenvolve, com
//! garantias honestas e reduzidas que `memory_status()` reporta como tais.

#![allow(unsafe_code)]

use std::alloc::{alloc_zeroed, dealloc, Layout};
use std::ptr::NonNull;

use crate::error::Error;

const PAGE: usize = 4096;

/// 🇺🇸 The page size this backend rounds to. 🇧🇷 O tamanho de página ao qual este backend arredonda.
pub fn page_size() -> usize {
    PAGE
}

/// 🇺🇸 A page-aligned, lockable allocation. 🇧🇷 Uma alocação alinhada a página e travável.
pub struct Region {
    data: NonNull<u8>,
    layout: Layout,
}

impl Region {
    /// 🇺🇸 Allocates zeroed pages able to hold `payload` bytes. 🇧🇷 Aloca páginas zeradas capazes de guardar `payload` bytes.
    pub fn map(payload: usize) -> Result<Self, Error> {
        let data_len = payload.checked_add(PAGE - 1).ok_or(Error::Allocation)? / PAGE * PAGE;
        let layout = Layout::from_size_align(data_len, PAGE).map_err(|_| Error::Allocation)?;
        // SAFETY: `layout` has a non-zero size (payload > 0 is enforced by the caller).
        let raw = unsafe { alloc_zeroed(layout) };
        let data = NonNull::new(raw).ok_or(Error::Allocation)?;
        Ok(Self { data, layout })
    }

    /// 🇺🇸 The data pages. 🇧🇷 As páginas de dados.
    pub fn data(&self) -> &[u8] {
        // SAFETY: `data` points at `layout.size()` initialized bytes owned by `self`.
        unsafe { std::slice::from_raw_parts(self.data.as_ptr(), self.layout.size()) }
    }

    /// 🇺🇸 Mutable view of the data pages. 🇧🇷 Visão mutável das páginas de dados.
    pub fn data_mut(&mut self) -> &mut [u8] {
        // SAFETY: as in `data`, and `&mut self` guarantees exclusivity.
        unsafe { std::slice::from_raw_parts_mut(self.data.as_ptr(), self.layout.size()) }
    }

    /// 🇺🇸 `VirtualLock` on the pages; `Err(0)` if refused (Windows gives no errno here).
    /// 🇧🇷 `VirtualLock` nas páginas; `Err(0)` se recusado (Windows não dá errno aqui).
    pub fn lock(&mut self) -> Result<(), i32> {
        // SAFETY: the range is exactly this allocation.
        if unsafe { memsec::mlock(self.data.as_ptr(), self.layout.size()) } {
            Ok(())
        } else {
            Err(0)
        }
    }

    /// 🇺🇸 `VirtualUnlock`; memsec zeroes first, which is harmless after our own zeroing.
    /// 🇧🇷 `VirtualUnlock`; memsec zera antes, o que é inofensivo depois do nosso próprio zerar.
    pub fn unlock(&mut self) {
        // SAFETY: the range is exactly this allocation.
        unsafe {
            memsec::munlock(self.data.as_ptr(), self.layout.size());
        }
    }
}

impl Drop for Region {
    fn drop(&mut self) {
        // SAFETY: `data`/`layout` are the pair returned by `alloc_zeroed` in `map`.
        unsafe { dealloc(self.data.as_ptr(), self.layout) };
    }
}
