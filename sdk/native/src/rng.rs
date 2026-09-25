//! 🇺🇸 The operating system's CSPRNG, as the `rand_core` traits dalek and ml-kem expect.
//!
//! There is exactly one source of randomness in this crate — `getrandom`, i.e.
//! `getrandom(2)`/`SecRandomCopyBytes`/`BCryptGenRandom` — and it is never
//! seeded, cached or wrapped in a userspace generator. A failure of the OS RNG
//! is unrecoverable: [`csprng`] panics rather than returning weaker bytes.
//!
//! 🇧🇷 O CSPRNG do sistema operacional, nos traits `rand_core` que dalek e ml-kem esperam.
//!
//! Há exatamente uma fonte de aleatoriedade neste crate — `getrandom`, isto é,
//! `getrandom(2)`/`SecRandomCopyBytes`/`BCryptGenRandom` — e ela nunca é
//! semeada, cacheada ou embrulhada num gerador de espaço de usuário. Falha do
//! RNG do SO é irrecuperável: [`csprng`] entra em panic em vez de devolver
//! bytes mais fracos.

use rand_core::{TryCryptoRng, TryRng, UnwrapErr};

use crate::error::Error;

/// 🇺🇸 Zero-sized handle on the OS RNG. 🇧🇷 Handle sem tamanho para o RNG do SO.
#[derive(Debug, Default, Clone, Copy)]
pub struct OsRandom;

impl TryRng for OsRandom {
    type Error = getrandom::Error;

    fn try_next_u32(&mut self) -> Result<u32, Self::Error> {
        getrandom::u32()
    }

    fn try_next_u64(&mut self) -> Result<u64, Self::Error> {
        getrandom::u64()
    }

    fn try_fill_bytes(&mut self, dst: &mut [u8]) -> Result<(), Self::Error> {
        getrandom::fill(dst)
    }
}

impl TryCryptoRng for OsRandom {}

/// 🇺🇸 The infallible view dalek/ml-kem take; panics if the OS RNG fails. 🇧🇷 A visão infalível que dalek/ml-kem recebem; panic se o RNG do SO falhar.
pub type Csprng = UnwrapErr<OsRandom>;

/// 🇺🇸 A fresh CSPRNG handle. 🇧🇷 Um handle de CSPRNG novo.
#[must_use]
pub fn csprng() -> Csprng {
    UnwrapErr(OsRandom)
}

/// 🇺🇸 Fills `dest` from the OS RNG, surfacing failure as [`Error::Random`]. 🇧🇷 Preenche `dest` do RNG do SO, expondo falha como [`Error::Random`].
pub fn fill(dest: &mut [u8]) -> Result<(), Error> {
    getrandom::fill(dest).map_err(Error::from)
}

/// 🇺🇸 `N` fresh random bytes. 🇧🇷 `N` bytes aleatórios novos.
pub fn random_array<const N: usize>() -> Result<[u8; N], Error> {
    let mut out = [0u8; N];
    fill(&mut out)?;
    Ok(out)
}
