//! 🇺🇸 The one error type of the crate, and its single Python face, `SecureError`.
//!
//! Every failure — a page that would not lock, a tag that did not verify, a
//! box already wiped — reaches Python as the same exception class. The SDK's
//! own `CryptoError` wraps it. Messages name *what* failed, never *why* in a
//! way that could act as an oracle: "did not open" covers a wrong key, a
//! wrong AAD and a tampered ciphertext alike, on purpose.
//!
//! 🇧🇷 O único tipo de erro do crate, e sua única face em Python, `SecureError`.
//!
//! Toda falha — uma página que não travou, uma tag que não verificou, uma
//! caixa já apagada — chega ao Python como a mesma classe de exceção. O
//! `CryptoError` do próprio SDK a embrulha. As mensagens dizem *o que* falhou,
//! nunca *por que* de um jeito que sirva de oráculo: "não abriu" cobre chave
//! errada, AAD errado e ciphertext adulterado igualmente, de propósito.

use std::fmt;

use pyo3::{create_exception, import_exception, PyErr};

// 🇺🇸 `SecureError` subclasses the SDK's own `CryptoError`, so a caller that
//    already catches `CryptoError` (`docs/PROTOCOL.md §12`) needs no second
//    `except` clause for failures that happen to originate in Rust.
// 🇧🇷 `SecureError` é subclasse do `CryptoError` do próprio SDK, então quem já
//    captura `CryptoError` (`docs/PROTOCOL.md §12`) não precisa de um segundo
//    `except` para falhas que por acaso nascem no Rust.
import_exception!(diagnos.errors, CryptoError);

create_exception!(
    diagnos._secure,
    SecureError,
    CryptoError,
    "🇺🇸 Raised by the native enclave: locking, key material or authentication failed. \
     🇧🇷 Lançada pelo enclave nativo: travamento, material de chave ou autenticação falhou."
);

/// 🇺🇸 Every way the enclave can fail. 🇧🇷 Todo jeito de o enclave falhar.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum Error {
    /// 🇺🇸 The box was wiped explicitly and can no longer be read. 🇧🇷 A caixa foi apagada explicitamente e não pode mais ser lida.
    Wiped,
    /// 🇺🇸 The box is empty because this process is a `fork()` child; secrets never survive a fork. 🇧🇷 A caixa está vazia porque este processo é filho de `fork()`; segredos nunca sobrevivem a um fork.
    WipedByFork,
    /// 🇺🇸 `mlock` refused under the `require` policy; carries the OS errno. 🇧🇷 `mlock` recusou sob a política `require`; carrega o errno do SO.
    LockFailed(i32),
    /// 🇺🇸 The OS would not hand out a page. 🇧🇷 O SO não entregou uma página.
    Allocation,
    /// 🇺🇸 A secret with zero bytes is a bug, not a value. 🇧🇷 Um segredo com zero bytes é bug, não valor.
    EmptySecret,
    /// 🇺🇸 A length did not match what the protocol fixes. 🇧🇷 Um tamanho não bateu com o que o protocolo fixa.
    InvalidLength {
        /// 🇺🇸 Which input. 🇧🇷 Qual entrada.
        what: &'static str,
        /// 🇺🇸 Bytes expected. 🇧🇷 Bytes esperados.
        expected: usize,
        /// 🇺🇸 Bytes received. 🇧🇷 Bytes recebidos.
        got: usize,
    },
    /// 🇺🇸 A public/secret key failed validation. 🇧🇷 Uma chave pública/secreta falhou na validação.
    InvalidKey,
    /// 🇺🇸 Authentication failed — wrong key, wrong AAD or tampering, indistinguishable by design. 🇧🇷 Autenticação falhou — chave errada, AAD errado ou adulteração, indistinguíveis de propósito.
    DidNotOpen,
    /// 🇺🇸 The stream already saw `TAG_FINAL`. 🇧🇷 O stream já viu `TAG_FINAL`.
    StreamFinished,
    /// 🇺🇸 A sealed JSON body was not the shape the protocol fixes. 🇧🇷 Um corpo JSON selado não tinha a forma que o protocolo fixa.
    Malformed(&'static str),
    /// 🇺🇸 The OS RNG failed; nothing safe can be produced. 🇧🇷 O RNG do SO falhou; nada seguro pode ser produzido.
    Random,
    /// 🇺🇸 A lock was poisoned by a panic in another thread. 🇧🇷 Um lock foi envenenado por um panic em outra thread.
    Poisoned,
    /// 🇺🇸 The platform lacks the primitive. 🇧🇷 A plataforma não tem a primitiva.
    Unsupported(&'static str),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Wiped => write!(f, "secret box was wiped · a caixa de segredo foi apagada"),
            Self::WipedByFork => write!(
                f,
                "secret box is empty in this fork() child; secrets never survive a fork · \
                 a caixa está vazia neste filho de fork(); segredos nunca sobrevivem a um fork"
            ),
            Self::LockFailed(errno) => write!(
                f,
                "mlock failed (errno {errno}) and DIAGNOS_MEMORY_LOCK=require; raise `ulimit -l` or grant \
                 CAP_IPC_LOCK · mlock falhou (errno {errno}) com DIAGNOS_MEMORY_LOCK=require; aumente \
                 `ulimit -l` ou conceda CAP_IPC_LOCK"
            ),
            Self::Allocation => {
                write!(f, "could not allocate a locked page · não foi possível alocar uma página travada")
            }
            Self::EmptySecret => write!(f, "a secret cannot be empty · um segredo não pode ser vazio"),
            Self::InvalidLength { what, expected, got } => {
                write!(f, "{what}: expected {expected} bytes, got {got} · esperava {expected} bytes, recebeu {got}")
            }
            Self::InvalidKey => write!(f, "key failed validation · chave falhou na validação"),
            Self::DidNotOpen => write!(f, "ciphertext did not open · ciphertext não abriu"),
            Self::StreamFinished => write!(f, "stream already finished · stream já terminou"),
            Self::Malformed(what) => write!(f, "malformed {what} · {what} malformado"),
            Self::Random => write!(f, "operating system RNG failed · RNG do sistema operacional falhou"),
            Self::Poisoned => write!(f, "internal lock poisoned · lock interno envenenado"),
            Self::Unsupported(what) => {
                write!(f, "{what} is not supported on this platform · {what} não é suportado nesta plataforma")
            }
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

/// 🇺🇸 Asserts an exact byte length, naming the input in the error. 🇧🇷 Garante um tamanho exato, nomeando a entrada no erro.
pub fn expect_len(what: &'static str, data: &[u8], expected: usize) -> Result<(), Error> {
    if data.len() == expected {
        Ok(())
    } else {
        Err(Error::InvalidLength { what, expected, got: data.len() })
    }
}
