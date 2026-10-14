//! [`EntropyPool`]: the vault's per-response seed, mixed into OS randomness, kept in a locked page.
//!
//! `docs/PROTOCOL.md §4`: every signed response carries a seed only this
//! session can open. Mixing it in defends against a cloned VM or container
//! whose OS RNG has not yet re-seeded — two clones share `os.urandom`'s first
//! bytes, but not the seed the vault sent to only one of them. The pool never
//! *replaces* the OS RNG: every 32-byte block is `SHA-256(os_random(32) ‖
//! state ‖ counter)`, so an all-zero state degrades to plain OS randomness,
//! never to something weaker. `state = SHA-256(seed)` — fixed size, so the
//! locked page never has to grow.

use std::sync::Mutex;

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use sha2::{Digest, Sha256};
use zeroize::Zeroizing;

use crate::buffer::read_bytes;
use crate::error::Error;
use crate::locked::LockedBuffer;
use crate::rng;
use crate::secret_box::SecretBox;

const STATE_BYTES: usize = 32;
const COUNTER_BYTES: usize = 8;
const POOL_BYTES: usize = STATE_BYTES + COUNTER_BYTES;
const BLOCK: usize = 32;

/// Stateful mixer; see the module docs.
#[pyclass(frozen, name = "EntropyPool", module = "diagnos._secure")]
pub struct EntropyPool {
    inner: Mutex<LockedBuffer>,
}

impl EntropyPool {
    fn fill(&self, out: &mut [u8]) -> Result<(), Error> {
        let mut guard = self.inner.lock()?;
        guard.with_bytes_mut(|pool| -> Result<(), Error> {
            let (state, counter_bytes) = pool.split_at_mut(STATE_BYTES);
            let mut counter_buf = [0u8; COUNTER_BYTES];
            counter_buf.copy_from_slice(counter_bytes);
            let mut counter = u64::from_be_bytes(counter_buf);
            for chunk in out.chunks_mut(BLOCK) {
                let mut fresh = Zeroizing::new([0u8; BLOCK]);
                rng::fill(&mut fresh[..])?;
                let mut hasher = Sha256::new();
                hasher.update(&fresh[..]);
                hasher.update(&state[..]);
                hasher.update(counter.to_be_bytes());
                let block = Zeroizing::new(hasher.finalize());
                chunk.copy_from_slice(&block[..chunk.len()]);
                counter = counter.wrapping_add(1);
            }
            counter_bytes.copy_from_slice(&counter.to_be_bytes());
            Ok(())
        })?
    }

    fn reseed(&self, seed: &[u8]) -> Result<(), Error> {
        let digest = Zeroizing::new(Sha256::digest(seed));
        let mut guard = self.inner.lock()?;
        guard.with_bytes_mut(|pool| {
            pool[..STATE_BYTES].copy_from_slice(&digest[..]);
            pool[STATE_BYTES..].fill(0);
        })
    }
}

#[pymethods]
impl EntropyPool {
    /// Starts unseeded: indistinguishable from the OS RNG until `mix()`.
    #[new]
    fn new() -> PyResult<Self> {
        Ok(Self { inner: Mutex::new(LockedBuffer::new(POOL_BYTES)?) })
    }

    /// Replaces the mixed-in seed (a `SecretBox` or bytes-like) and resets the counter.
    fn mix(&self, seed: &Bound<'_, PyAny>) -> PyResult<()> {
        if let Ok(secret) = seed.cast::<SecretBox>() {
            let secret: &SecretBox = secret.get();
            let copy = secret.to_zeroizing()?;
            return Ok(self.reseed(&copy)?);
        }
        let seed = read_bytes(seed)?;
        Ok(self.reseed(&seed)?)
    }

    /// `n` bytes for public values: nonces, salts, ids.
    fn random<'py>(&self, py: Python<'py>, n: usize) -> PyResult<Bound<'py, PyBytes>> {
        let mut out = vec![0u8; n];
        self.fill(&mut out)?;
        Ok(PyBytes::new(py, &out))
    }

    /// `n` bytes born in a locked box: a new DEK never touches the Python heap.
    fn random_secret(&self, n: usize) -> PyResult<SecretBox> {
        let mut buffer = LockedBuffer::new(n)?;
        buffer.with_bytes_mut(|out| self.fill(out))??;
        Ok(SecretBox::from_locked(buffer))
    }

    fn __repr__(&self) -> String {
        "EntropyPool(<state redacted>)".to_owned()
    }
}
