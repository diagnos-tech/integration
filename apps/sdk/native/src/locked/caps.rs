//! 🇺🇸 `CAP_IPC_LOCK` for the calling thread: raise it from *permitted* to *effective* when the runtime granted it.
//!
//! A non-root process can `mlock` more than `RLIMIT_MEMLOCK` only with
//! `CAP_IPC_LOCK` in its *effective* set. Container images carry it as a
//! file capability on the interpreter, and there are two ways to spell
//! that: `cap_ipc_lock=+ep` makes the kernel refuse to `exec` the binary at
//! all when the container was not granted the capability (`EPERM`, before
//! the first line of Python), while `cap_ipc_lock=+p` always execs and
//! leaves the capability merely *permitted*, for the program to raise
//! itself. This crate expects `+p` and does the raising here — so a
//! deployment that forgets `cap_add: [IPC_LOCK]` degrades to best-effort
//! locking with a warning instead of a container that never starts.
//!
//! Capabilities are per thread on Linux, so the raise happens in whichever
//! thread is about to call `mlock`, cached per thread; two syscalls, once.
//!
//! 🇧🇷 `CAP_IPC_LOCK` para a thread que chama: sobe de *permitted* para *effective* quando o runtime a concedeu.
//!
//! Um processo sem root só consegue `mlock` além do `RLIMIT_MEMLOCK` com
//! `CAP_IPC_LOCK` no conjunto *effective*. Imagens de container a carregam
//! como capability de arquivo no interpretador, e há dois jeitos de
//! escrever isso: `cap_ipc_lock=+ep` faz o kernel se recusar a executar o
//! binário quando o container não recebeu a capability (`EPERM`, antes da
//! primeira linha de Python), enquanto `cap_ipc_lock=+p` sempre executa e
//! deixa a capability apenas *permitted*, para o programa subir sozinho.
//! Este crate espera `+p` e faz a subida aqui — então um deployment que
//! esquece `cap_add: [IPC_LOCK]` degrada para travamento best-effort com
//! aviso, em vez de um container que nunca sobe.
//!
//! Capabilities são por thread no Linux, então a subida acontece na thread
//! que está prestes a chamar `mlock`, com cache por thread; duas syscalls,
//! uma vez.

#![allow(unsafe_code)]

use std::cell::Cell;

const CAP_IPC_LOCK: u32 = 14;
const LINUX_CAPABILITY_VERSION_3: u32 = 0x2008_0522;

#[repr(C)]
struct Header {
    version: u32,
    pid: i32,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Data {
    effective: u32,
    permitted: u32,
    inheritable: u32,
}

thread_local! {
    static RAISED: Cell<bool> = const { Cell::new(false) };
}

fn capget() -> Option<[Data; 2]> {
    let mut header = Header { version: LINUX_CAPABILITY_VERSION_3, pid: 0 };
    let mut data = [Data::default(); 2];
    // SAFETY: version 3 of the capability ABI writes exactly two `Data`
    // structs; both pointers are valid for the duration of the call.
    let rc = unsafe { libc::syscall(libc::SYS_capget, &raw mut header, data.as_mut_ptr()) };
    (rc == 0).then_some(data)
}

/// 🇺🇸 `(permitted, effective)` for `CAP_IPC_LOCK` in the calling thread; `None` if the kernel would not say.
/// 🇧🇷 `(permitted, effective)` de `CAP_IPC_LOCK` na thread que chama; `None` se o kernel não disser.
#[must_use]
pub fn ipc_lock_state() -> Option<(bool, bool)> {
    let bit = 1u32 << CAP_IPC_LOCK;
    capget().map(|data| (data[0].permitted & bit != 0, data[0].effective & bit != 0))
}

/// 🇺🇸 Makes `CAP_IPC_LOCK` effective for this thread if it is permitted; returns whether it is effective now.
/// 🇧🇷 Torna `CAP_IPC_LOCK` efetiva para esta thread se estiver permitida; devolve se está efetiva agora.
pub fn ensure_ipc_lock_effective() -> bool {
    if RAISED.with(Cell::get) {
        return true;
    }
    let Some(mut data) = capget() else {
        return false;
    };
    let bit = 1u32 << CAP_IPC_LOCK;
    if data[0].effective & bit != 0 {
        RAISED.with(|raised| raised.set(true));
        return true;
    }
    if data[0].permitted & bit == 0 {
        return false;
    }
    data[0].effective |= bit;
    let mut header = Header { version: LINUX_CAPABILITY_VERSION_3, pid: 0 };
    // SAFETY: same ABI as `capget`; raising a permitted capability into the
    // effective set needs no privilege and touches only this thread.
    let rc = unsafe { libc::syscall(libc::SYS_capset, &raw mut header, data.as_ptr()) };
    let effective = rc == 0;
    if effective {
        RAISED.with(|raised| raised.set(true));
    }
    effective
}
