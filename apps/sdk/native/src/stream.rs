//! 🇺🇸 Python faces of the secretstream: [`SecretStreamPush`] and [`SecretStreamPull`], state in a locked page.
//!
//! The Python side owns framing (`[len u32 BE][chunk]`) and chunking; these
//! classes own exactly one thing each: a 44-byte state that never leaves a
//! locked page, advanced one chunk at a time. Chunk bodies are content, not
//! secrets, so they cross the boundary as plain `bytes`, and the work runs
//! with the GIL released — a 1 MiB chunk is the rule, not the exception.
//!
//! 🇧🇷 Faces Python do secretstream: [`SecretStreamPush`] e [`SecretStreamPull`], estado numa página travada.
//!
//! O lado Python é dono do framing (`[len u32 BE][chunk]`) e do fatiamento;
//! estas classes são donas de exatamente uma coisa cada: um estado de 44
//! bytes que nunca sai de uma página travada, avançado um chunk por vez.
//! Corpos de chunk são conteúdo, não segredo, então cruzam a fronteira como
//! `bytes` comuns, e o trabalho roda com a GIL liberada — um chunk de 1 MiB é
//! a regra, não a exceção.

use std::sync::Mutex;

use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::buffer::{read_bytes, read_optional};
use crate::error::Error;
use crate::locked::LockedBuffer;
use crate::rng;
use crate::secret_box::SecretBox;
use crate::secretstream::{self, HEADER_BYTES, STATE_BYTES, TAG_FINAL, TAG_MESSAGE};

struct StreamState {
    state: LockedBuffer,
    finished: bool,
}

impl StreamState {
    fn new(key: &SecretBox, header: &[u8]) -> Result<Self, Error> {
        let mut state = LockedBuffer::new(STATE_BYTES)?;
        key.with_bytes(|key| state.with_bytes_mut(|state| secretstream::init(state, key, header)))???;
        Ok(Self { state, finished: false })
    }
}

/// 🇺🇸 Encrypting side: `header` first, then `push(chunk, final=...)` per chunk.
/// 🇧🇷 Lado que cifra: `header` primeiro, depois `push(chunk, final=...)` por chunk.
#[pyclass(frozen, name = "SecretStreamPush", module = "diagnos._secure")]
pub struct SecretStreamPush {
    header: [u8; HEADER_BYTES],
    inner: Mutex<StreamState>,
}

#[pymethods]
impl SecretStreamPush {
    /// 🇺🇸 Starts a stream under `key` with a random 24-byte header. 🇧🇷 Inicia um stream sob `key` com um header aleatório de 24 bytes.
    #[new]
    fn new(key: PyRef<'_, SecretBox>) -> PyResult<Self> {
        let header = rng::random_array::<HEADER_BYTES>()?;
        let state = StreamState::new(&key, &header)?;
        Ok(Self { header, inner: Mutex::new(state) })
    }

    /// 🇺🇸 The 24-byte header the reader needs first. 🇧🇷 O header de 24 bytes que o leitor precisa primeiro.
    #[getter]
    fn header<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.header)
    }

    /// 🇺🇸 Whether the final chunk was already pushed. 🇧🇷 Se o chunk final já foi empurrado.
    #[getter]
    fn is_finished(&self) -> PyResult<bool> {
        Ok(self.inner.lock().map_err(Error::from)?.finished)
    }

    /// 🇺🇸 Encrypts one chunk; `final=True` marks the last one, after which the stream refuses more.
    /// 🇧🇷 Cifra um chunk; `final=True` marca o último, depois do qual o stream recusa mais.
    #[pyo3(signature = (message, *, r#final = false, ad = None))]
    fn push<'py>(
        &self,
        py: Python<'py>,
        message: &Bound<'py, PyAny>,
        r#final: bool,
        ad: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let message = read_bytes(message)?;
        let ad = read_optional(ad)?;
        let tag = if r#final { TAG_FINAL } else { TAG_MESSAGE };
        let sealed = py.detach(|| -> Result<Vec<u8>, Error> {
            let mut guard = self.inner.lock()?;
            if guard.finished {
                return Err(Error::StreamFinished);
            }
            let out = guard.state.with_bytes_mut(|state| {
                secretstream::push(state, &message, ad.as_deref().map_or(&[][..], |a| &a[..]), tag)
            })??;
            guard.finished = r#final;
            Ok(out)
        })?;
        Ok(PyBytes::new(py, &sealed))
    }
}

/// 🇺🇸 Decrypting side: built from `key` and the header, then `pull(chunk)` per chunk → `(plaintext, is_final)`.
/// 🇧🇷 Lado que decifra: construído de `key` e do header, depois `pull(chunk)` por chunk → `(texto claro, é_final)`.
#[pyclass(frozen, name = "SecretStreamPull", module = "diagnos._secure")]
pub struct SecretStreamPull {
    inner: Mutex<StreamState>,
}

#[pymethods]
impl SecretStreamPull {
    /// 🇺🇸 Opens a stream under `key` from its 24-byte header. 🇧🇷 Abre um stream sob `key` a partir do header de 24 bytes.
    #[new]
    fn new(key: PyRef<'_, SecretBox>, header: &Bound<'_, PyAny>) -> PyResult<Self> {
        let header = read_bytes(header)?;
        let state = StreamState::new(&key, &header)?;
        Ok(Self { inner: Mutex::new(state) })
    }

    /// 🇺🇸 Whether `TAG_FINAL` was already seen. 🇧🇷 Se `TAG_FINAL` já foi visto.
    #[getter]
    fn is_finished(&self) -> PyResult<bool> {
        Ok(self.inner.lock().map_err(Error::from)?.finished)
    }

    /// 🇺🇸 Authenticates and decrypts one chunk; refuses anything after the final one.
    /// 🇧🇷 Autentica e decifra um chunk; recusa qualquer coisa depois do final.
    #[pyo3(signature = (chunk, *, ad = None))]
    fn pull<'py>(
        &self,
        py: Python<'py>,
        chunk: &Bound<'py, PyAny>,
        ad: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<(Bound<'py, PyBytes>, bool)> {
        let chunk = read_bytes(chunk)?;
        let ad = read_optional(ad)?;
        let (message, tag) = py.detach(|| -> Result<(Vec<u8>, u8), Error> {
            let mut guard = self.inner.lock()?;
            if guard.finished {
                return Err(Error::StreamFinished);
            }
            let (message, tag) = guard.state.with_bytes_mut(|state| {
                secretstream::pull(state, &chunk, ad.as_deref().map_or(&[][..], |a| &a[..]))
            })??;
            guard.finished = tag == TAG_FINAL;
            Ok((message, tag))
        })?;
        Ok((PyBytes::new(py, &message), tag == TAG_FINAL))
    }
}
