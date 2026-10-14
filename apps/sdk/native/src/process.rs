//! Process-wide hardening and introspection: `harden_process()` and `memory_status()`.
//!
//! Locked pages protect a secret from the disk; they do not protect it from
//! another process with `ptrace` rights or from a core dump of the pages that
//! were *not* locked (the Python heap holding a transient copy). Hardening
//! closes those two doors for the whole process: `PR_SET_DUMPABLE = 0`
//! (Linux: no core dumps, and no `ptrace` attach from same-uid processes),
//! `RLIMIT_CORE = 0` (any Unix), `PT_DENY_ATTACH` (macOS). It also raises
//! the soft `RLIMIT_MEMLOCK` to the hard limit, which is free and often the
//! difference between "locked" and "best-effort" in a container. Nothing
//! here needs privileges, and nothing here is ever fatal: the report says
//! what was applied, and the SDK logs it.

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::locked::{self, LockPolicy};

/// Soft/hard `RLIMIT_MEMLOCK` in bytes; `None` means unlimited or unknown.
#[derive(Debug, Clone, Copy, Default)]
pub struct MemlockLimit {
    /// Current (soft) limit.
    pub soft: Option<u64>,
    /// Maximum (hard) limit.
    pub hard: Option<u64>,
}

#[cfg(unix)]
mod unix {
    #![allow(unsafe_code)]

    use super::MemlockLimit;

    // `rlim_t` is `u64` on the tier-1 Unix targets but not guaranteed to
    // be; the conversion is a no-op here and the portability net elsewhere.
    #[allow(clippy::useless_conversion)]
    fn as_option(value: libc::rlim_t) -> Option<u64> {
        if value == libc::RLIM_INFINITY {
            None
        } else {
            Some(u64::try_from(value).unwrap_or(u64::MAX))
        }
    }

    pub fn memlock_limit() -> MemlockLimit {
        let mut limit = libc::rlimit { rlim_cur: 0, rlim_max: 0 };
        // SAFETY: `limit` is a valid out-pointer for the duration of the call.
        if unsafe { libc::getrlimit(libc::RLIMIT_MEMLOCK, &raw mut limit) } != 0 {
            return MemlockLimit::default();
        }
        MemlockLimit { soft: as_option(limit.rlim_cur), hard: as_option(limit.rlim_max) }
    }

    /// Raises the soft memlock limit to the hard one; returns whether anything changed.
    pub fn raise_memlock() -> bool {
        let mut limit = libc::rlimit { rlim_cur: 0, rlim_max: 0 };
        // SAFETY: valid out-pointer; a second call with the same struct is a plain setrlimit.
        unsafe {
            if libc::getrlimit(libc::RLIMIT_MEMLOCK, &raw mut limit) != 0 || limit.rlim_cur == limit.rlim_max {
                return false;
            }
            limit.rlim_cur = limit.rlim_max;
            libc::setrlimit(libc::RLIMIT_MEMLOCK, &raw const limit) == 0
        }
    }

    pub fn disable_core_dumps() -> bool {
        let limit = libc::rlimit { rlim_cur: 0, rlim_max: 0 };
        // SAFETY: `limit` is a valid, fully initialized struct.
        unsafe { libc::setrlimit(libc::RLIMIT_CORE, &raw const limit) == 0 }
    }

    #[cfg(target_os = "linux")]
    pub fn restrict_ptrace() -> bool {
        // SAFETY: prctl with PR_SET_DUMPABLE takes plain integers.
        unsafe { libc::prctl(libc::PR_SET_DUMPABLE, 0, 0, 0, 0) == 0 }
    }

    #[cfg(target_os = "macos")]
    pub fn restrict_ptrace() -> bool {
        // SAFETY: PT_DENY_ATTACH ignores every other argument.
        unsafe { libc::ptrace(libc::PT_DENY_ATTACH, 0, std::ptr::null_mut(), 0) == 0 }
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos")))]
    pub fn restrict_ptrace() -> bool {
        false
    }
}

#[cfg(not(unix))]
mod unix {
    use super::MemlockLimit;

    pub fn memlock_limit() -> MemlockLimit {
        MemlockLimit::default()
    }
    pub fn raise_memlock() -> bool {
        false
    }
    pub fn disable_core_dumps() -> bool {
        false
    }
    pub fn restrict_ptrace() -> bool {
        false
    }
}

fn limit_item(value: Option<u64>) -> Option<u64> {
    value
}

/// Applies every hardening step available on this platform; returns what took effect. Idempotent.
#[pyfunction]
pub fn harden_process(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let memlock_raised = unix::raise_memlock();
    let core_dumps_disabled = unix::disable_core_dumps();
    let ptrace_restricted = unix::restrict_ptrace();
    let limit = unix::memlock_limit();
    let report = PyDict::new(py);
    report.set_item("platform", std::env::consts::OS)?;
    report.set_item("core_dumps_disabled", core_dumps_disabled)?;
    report.set_item("ptrace_restricted", ptrace_restricted)?;
    report.set_item("memlock_soft_raised", memlock_raised)?;
    report.set_item("memlock_soft", limit_item(limit.soft))?;
    report.set_item("memlock_hard", limit_item(limit.hard))?;
    Ok(report)
}

/// What the enclave can and cannot guarantee right now, for logs and `diagnos status`.
#[pyfunction]
pub fn memory_status(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let stats = locked::stats();
    let limit = unix::memlock_limit();
    let status = PyDict::new(py);
    status.set_item("platform", std::env::consts::OS)?;
    status.set_item("backend", if cfg!(unix) { "mmap+mlock" } else { "virtuallock" })?;
    status.set_item("guard_pages", cfg!(unix))?;
    status.set_item("wipe_on_fork", cfg!(target_os = "linux"))?;
    status.set_item("page_size", stats.page_size)?;
    status.set_item("lock_policy", LockPolicy::current().name())?;
    status.set_item("live_secrets", stats.live)?;
    status.set_item("unlocked_allocations", stats.unlocked)?;
    status.set_item("last_lock_errno", stats.last_lock_errno)?;
    status.set_item("memlock_soft", limit_item(limit.soft))?;
    status.set_item("memlock_hard", limit_item(limit.hard))?;
    let (permitted, effective) = ipc_lock_state();
    status.set_item("ipc_lock_permitted", permitted)?;
    status.set_item("ipc_lock_effective", effective)?;
    Ok(status)
}

/// `CAP_IPC_LOCK` (permitted, effective) for this thread on Linux; `(None, None)` elsewhere.
fn ipc_lock_state() -> (Option<bool>, Option<bool>) {
    #[cfg(target_os = "linux")]
    {
        match locked::caps::ipc_lock_state() {
            Some((permitted, effective)) => (Some(permitted), Some(effective)),
            None => (None, None),
        }
    }
    #[cfg(not(target_os = "linux"))]
    {
        (None, None)
    }
}
