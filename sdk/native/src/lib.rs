//! 🇺🇸 `diagnos._secure` — the memory enclave the Python SDK keeps its secrets in.
//!
//! Python cannot promise where a secret lives: `bytes` are immutable and
//! interned, a `bytearray` that grows leaves its old copy behind for the
//! garbage collector, and any page of the heap may be swapped to disk or
//! written into a core dump. This crate gives the SDK one type, [`SecretBox`],
//! whose bytes are allocated in pages that are locked in RAM (`mlock`),
//! excluded from core dumps, fenced by guard pages, wiped on fork and zeroed
//! the moment the box is dropped — and whose bytes never cross back into the
//! Python heap, because every operation that needs them (HMAC, HKDF, AES-GCM,
//! X25519 + ML-KEM, secretstream) runs here, in Rust, against the locked page.
//!
//! The crate is deliberately small: it is a *boundary*, not a crypto library.
//! Every primitive is a thin, audited RustCrypto/dalek implementation; every
//! format is the one `docs/PROTOCOL.md` pins and the TypeScript reference
//! produces, byte for byte (`tests/vectors.rs` proves it).
//!
//! 🇧🇷 `diagnos._secure` — o enclave de memória em que o SDK Python guarda seus segredos.
//!
//! Python não consegue prometer onde um segredo mora: `bytes` são imutáveis e
//! internados, um `bytearray` que cresce deixa a cópia antiga para o coletor
//! de lixo, e qualquer página do heap pode ir para o swap ou para um core
//! dump. Este crate dá ao SDK um tipo, [`SecretBox`], cujos bytes vivem em
//! páginas travadas na RAM (`mlock`), excluídas de core dumps, cercadas por
//! guard pages, apagadas no fork e zeradas no instante em que a caixa é
//! descartada — e cujos bytes nunca voltam ao heap do Python, porque toda
//! operação que precisa deles (HMAC, HKDF, AES-GCM, X25519 + ML-KEM,
//! secretstream) roda aqui, em Rust, contra a página travada.
//!
//! O crate é pequeno de propósito: é uma *fronteira*, não uma biblioteca de
//! criptografia. Toda primitiva é uma implementação fina e auditada do
//! RustCrypto/dalek; todo formato é o que `docs/PROTOCOL.md` fixa e a
//! referência em TypeScript produz, byte a byte (`tests/vectors.rs` prova).

#![deny(unsafe_code)]
#![deny(missing_docs)]
#![warn(clippy::all, clippy::pedantic)]
// 🇺🇸 Pedantic lints that fight the pyo3 shape or the bilingual docs: `#[pymethods]`
//    dunders must take `&self`; `# Errors` sections would duplicate the one
//    `Error` enum; product names (OpenBao, HybridSeal) are prose, not code.
// 🇧🇷 Lints pedantes que brigam com a forma do pyo3 ou com a doc bilíngue:
//    dunders de `#[pymethods]` precisam de `&self`; seções `# Errors` duplicariam
//    o único enum `Error`; nomes de produto (OpenBao, HybridSeal) são prosa,
//    não código.
#![allow(
    clippy::module_name_repetitions,
    clippy::needless_pass_by_value,
    clippy::unused_self,
    clippy::missing_errors_doc,
    clippy::doc_markdown,
    clippy::similar_names
)]

pub mod aead;
mod buffer;
pub mod entropy;
pub mod error;
pub mod hybrid;
pub mod kdf;
pub mod locked;
pub mod process;
pub mod rng;
pub mod secret_box;
pub mod secretstream;
pub mod stream;

pub use error::Error;
pub use secret_box::SecretBox;

use pyo3::prelude::*;

/// 🇺🇸 Module entry point: registers the classes, functions and constants Python sees.
/// 🇧🇷 Ponto de entrada do módulo: registra as classes, funções e constantes que o Python vê.
#[pymodule]
fn _secure(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<secret_box::SecretBox>()?;
    m.add_class::<hybrid::HybridKeyPair>()?;
    m.add_class::<stream::SecretStreamPush>()?;
    m.add_class::<stream::SecretStreamPull>()?;
    m.add_class::<entropy::EntropyPool>()?;
    m.add_function(wrap_pyfunction!(hybrid::seal_hybrid, m)?)?;
    m.add_function(wrap_pyfunction!(process::harden_process, m)?)?;
    m.add_function(wrap_pyfunction!(process::memory_status, m)?)?;
    m.add("SecureError", m.py().get_type::<error::SecureError>())?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("SECRETSTREAM_HEADER_BYTES", secretstream::HEADER_BYTES)?;
    m.add("SECRETSTREAM_ABYTES", secretstream::ABYTES)?;
    m.add("X25519_PUBLIC_BYTES", hybrid::X25519_PUBLIC_BYTES)?;
    m.add("X25519_SECRET_BYTES", hybrid::X25519_SECRET_BYTES)?;
    m.add("MLKEM768_PUBLIC_BYTES", hybrid::MLKEM768_PUBLIC_BYTES)?;
    m.add("MLKEM768_SECRET_BYTES", hybrid::MLKEM768_SECRET_BYTES)?;
    m.add("MLKEM768_CIPHERTEXT_BYTES", hybrid::MLKEM768_CIPHERTEXT_BYTES)?;
    Ok(())
}
