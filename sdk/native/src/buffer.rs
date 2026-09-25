//! 🇺🇸 Reading Python buffers (`bytes`, `bytearray`, `memoryview`) into zeroizing Rust memory.
//!
//! Two rules make the rest of the crate simple. First, anything Python hands
//! in is copied into a [`Zeroizing`] `Vec` so the working copy dies clean,
//! whatever the caller does with the original. Second, when the caller's
//! object is *writable* (a `bytearray`, a writable `memoryview`), ingesting it
//! as a secret also zeroes the source in place — the caller asked for the
//! secret to move into the enclave, and leaving the clear copy behind would
//! defeat the point. `bytes` and `str` cannot be zeroed; `bytes` is accepted
//! (for test vectors and OpenBao restores) and documented as a copy, `str`
//! is rejected outright.
//!
//! 🇧🇷 Leitura de buffers Python (`bytes`, `bytearray`, `memoryview`) em memória Rust que se zera.
//!
//! Duas regras simplificam o resto do crate. Primeira, tudo que o Python
//! entrega é copiado para um `Vec` [`Zeroizing`], para a cópia de trabalho
//! morrer limpa, faça o que fizer quem chamou com o original. Segunda, quando
//! o objeto de quem chamou é *gravável* (um `bytearray`, um `memoryview`
//! gravável), ingeri-lo como segredo também zera a origem no lugar — quem
//! chamou pediu que o segredo se movesse para o enclave, e deixar a cópia em
//! claro para trás anularia o propósito. `bytes` e `str` não podem ser
//! zerados; `bytes` é aceito (para vetores de teste e restores do OpenBao) e
//! documentado como cópia, `str` é recusado de cara.

#![allow(unsafe_code)]

use pyo3::buffer::PyBuffer;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use zeroize::Zeroizing;

/// 🇺🇸 Copies any buffer-protocol object into zeroizing memory. 🇧🇷 Copia qualquer objeto com buffer protocol para memória que se zera.
pub fn read_bytes(obj: &Bound<'_, PyAny>) -> PyResult<Zeroizing<Vec<u8>>> {
    let buffer = typed_buffer(obj)?;
    Ok(Zeroizing::new(buffer.to_vec(obj.py())?))
}

/// 🇺🇸 `read_bytes` for an optional argument; `None` stays `None`. 🇧🇷 `read_bytes` para argumento opcional; `None` continua `None`.
pub fn read_optional(obj: Option<&Bound<'_, PyAny>>) -> PyResult<Option<Zeroizing<Vec<u8>>>> {
    obj.map(read_bytes).transpose()
}

/// 🇺🇸 Copies the buffer, then zeroes the source if it is writable and contiguous; returns whether it did.
/// 🇧🇷 Copia o buffer, depois zera a origem se ela for gravável e contígua; devolve se conseguiu.
pub fn take_bytes(obj: &Bound<'_, PyAny>) -> PyResult<(Zeroizing<Vec<u8>>, bool)> {
    let buffer = typed_buffer(obj)?;
    let copy = Zeroizing::new(buffer.to_vec(obj.py())?);
    let wiped = wipe_source(&buffer);
    Ok((copy, wiped))
}

fn typed_buffer(obj: &Bound<'_, PyAny>) -> PyResult<PyBuffer<u8>> {
    if obj.is_instance_of::<pyo3::types::PyString>() {
        return Err(PyTypeError::new_err(
            "expected a bytes-like object, got str; encode it first · esperava um objeto tipo bytes, recebeu str; codifique antes",
        ));
    }
    PyBuffer::<u8>::get(obj)
}

/// 🇺🇸 Overwrites a writable, C-contiguous buffer with zeros, in place.
///
/// The buffer view is held for the duration of the write (`PyBuffer` keeps
/// the exporter's `Py_buffer` alive), so the memory cannot be freed or
/// resized underneath the write; the GIL is held by the caller, so no other
/// Python thread observes a half-zeroed buffer.
///
/// 🇧🇷 Sobrescreve com zeros, no lugar, um buffer gravável e C-contíguo.
///
/// A visão do buffer é mantida durante a escrita (`PyBuffer` segura o
/// `Py_buffer` do exportador), então a memória não pode ser liberada nem
/// redimensionada por baixo da escrita; a GIL está com quem chama, então
/// nenhuma outra thread Python observa um buffer meio zerado.
fn wipe_source(buffer: &PyBuffer<u8>) -> bool {
    if buffer.readonly() || !buffer.is_c_contiguous() {
        return false;
    }
    let len = buffer.len_bytes();
    if len == 0 {
        return true;
    }
    // SAFETY: `buf_ptr` is a valid, writable, C-contiguous region of exactly
    // `len_bytes` bytes for as long as `buffer` lives (see the doc comment).
    unsafe { std::ptr::write_bytes(buffer.buf_ptr().cast::<u8>(), 0, len) };
    true
}
