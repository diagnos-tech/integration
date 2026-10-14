//! The one error type of the crate, and its single Python face, `SecureError`.
//!
//! Every failure — a page that would not lock, a tag that did not verify, a
//! box already wiped — reaches Python as the same exception class. The SDK's
//! own `CryptoError` is its base class. Messages name *what* failed, never
//! *why* in a way that could act as an oracle: "did not open" covers a wrong
//! key, a wrong AAD and a tampered ciphertext alike, on purpose.

use std::fmt;

use pyo3::{create_exception, import_exception, PyErr};

// `SecureError` subclasses the SDK's own `CryptoError`, so a caller that
// already catches `CryptoError` (`docs/PROTOCOL.md §12`) needs no second
// `except` clause for failures that happen to originate in Rust.
import_exception!(diagnos.errors, CryptoError);

create_exception!(
    diagnos._secure,
    SecureError,
    CryptoError,
    "Raised by the native enclave when locking, key material or authentication fails."
);

/// Every way the enclave can fail.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum Error {
    /// The box was wiped explicitly and can no longer be read.
    Wiped,
    /// The box is empty because this process is a `fork()` child; secrets never survive a fork.
    WipedByFork,
    /// `mlock` refused under the `require` policy; carries the OS errno.
    LockFailed(i32),
    /// The OS would not hand out a page.
    Allocation,
    /// A secret with zero bytes is a bug, not a value.
    EmptySecret,
    /// A length did not match what the protocol fixes.
    InvalidLength {
        /// Which input.
        what: &'static str,
        /// Bytes expected.
        expected: usize,
        /// Bytes received.
        got: usize,
    },
    /// A public/secret key failed validation.
    InvalidKey,
    /// Authentication failed — wrong key, wrong AAD or tampering, indistinguishable by design.
    DidNotOpen,
    /// The stream already saw `TAG_FINAL`.
    StreamFinished,
    /// A sealed JSON body was not the shape the protocol fixes.
    Malformed(&'static str),
    /// The OS RNG failed; nothing safe can be produced.
    Random,
    /// A lock was poisoned by a panic in another thread.
    Poisoned,
    /// The platform lacks the primitive.
    Unsupported(&'static str),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Wiped => write!(f, "secret box was wiped"),
            Self::WipedByFork => write!(f, "secret box is empty in this fork() child; secrets never survive a fork"),
            Self::LockFailed(errno) => write!(
                f,
                "mlock failed (errno {errno}) and DIAGNOS_MEMORY_LOCK=require; raise `ulimit -l` or grant \
                 CAP_IPC_LOCK"
            ),
            Self::Allocation => write!(f, "could not allocate a locked page"),
            Self::EmptySecret => write!(f, "a secret cannot be empty"),
            Self::InvalidLength { what, expected, got } => write!(f, "{what}: expected {expected} bytes, got {got}"),
            Self::InvalidKey => write!(f, "key failed validation"),
            Self::DidNotOpen => write!(f, "ciphertext did not open"),
            Self::StreamFinished => write!(f, "stream already finished"),
            Self::Malformed(what) => write!(f, "malformed {what}"),
            Self::Random => write!(f, "operating system RNG failed"),
            Self::Poisoned => write!(f, "internal lock poisoned"),
            Self::Unsupported(what) => write!(f, "{what} is not supported on this platform"),
        }
    }
}

impl std::error::Error for Error {}

impl From<Error> for PyErr {
    fn from(error: Error) -> Self {
        SecureError::new_err(error.to_string())
    }
}

impl From<getrandom::Error> for Error {
    fn from(_: getrandom::Error) -> Self {
        Self::Random
    }
}

impl<T> From<std::sync::PoisonError<T>> for Error {
    fn from(_: std::sync::PoisonError<T>) -> Self {
        Self::Poisoned
    }
}

/// Asserts an exact byte length, naming the input in the error.
pub fn expect_len(what: &'static str, data: &[u8], expected: usize) -> Result<(), Error> {
    if data.len() == expected {
        Ok(())
    } else {
        Err(Error::InvalidLength { what, expected, got: data.len() })
    }
}
