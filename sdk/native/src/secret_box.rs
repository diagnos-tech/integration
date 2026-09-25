//! 🇺🇸 [`SecretBox`]: the Python-visible handle on a locked secret, and the operations that use it without exposing it.
//!
//! Design rules, in order of importance:
//! 1. **No way back to `bytes`.** There is no `__bytes__`, no buffer
//!    protocol, no `__getitem__`. The only exit is [`SecretBox::reveal`],
//!    which returns a `bytearray` the caller is expected to zero, and which
//!    exists solely for the OpenBao export path.
//! 2. **Nothing leaks by accident.** `repr` is redacted, `pickle`/`copy`/
//!    `deepcopy` raise, hashing is disabled, equality is constant-time.
//! 3. **Locks are never nested.** Two boxes are never locked at the same
//!    time — a second operand is copied into zeroizing memory first — so
//!    `a.op(a)` cannot deadlock and no lock ordering has to exist.
//!
//! 🇧🇷 [`SecretBox`]: o handle visível ao Python de um segredo travado, e as operações que o usam sem expô-lo.
//!
//! Regras de desenho, em ordem de importância:
//! 1. **Sem caminho de volta para `bytes`.** Não há `__bytes__`, nem buffer
//!    protocol, nem `__getitem__`. A única saída é [`SecretBox::reveal`], que
//!    devolve um `bytearray` que quem chama deve zerar, e que existe só para
//!    o caminho de exportação ao OpenBao.
//! 2. **Nada vaza por acidente.** `repr` é redigido, `pickle`/`copy`/
//!    `deepcopy` lançam, hash é desligado, igualdade é em tempo constante.
//! 3. **Locks nunca se aninham.** Duas caixas nunca ficam travadas ao mesmo
//!    tempo — um segundo operando é copiado antes para memória que se zera —
//!    então `a.op(a)` não trava e nenhuma ordem de lock precisa existir.

use std::sync::Mutex;

use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyBytes};
use subtle::ConstantTimeEq;
use zeroize::Zeroizing;

use crate::buffer::{read_bytes, read_optional, take_bytes};
use crate::error::Error;
use crate::hybrid::b64url_decode;
use crate::locked::LockedBuffer;
use crate::{aead, kdf, rng};

/// 🇺🇸 Bytes that live only in locked memory; see the module docs for the rules.
/// 🇧🇷 Bytes que vivem só em memória travada; veja a doc do módulo para as regras.
#[pyclass(frozen, name = "SecretBox", module = "diagnos._secure")]
pub struct SecretBox {
    inner: Mutex<LockedBuffer>,
}

impl SecretBox {
    /// 🇺🇸 Wraps an existing buffer. 🇧🇷 Embrulha um buffer existente.
    #[must_use]
    pub fn from_locked(buffer: LockedBuffer) -> Self {
        Self { inner: Mutex::new(buffer) }
    }

    /// 🇺🇸 Copies `data` into a fresh locked buffer. 🇧🇷 Copia `data` para um buffer travado novo.
    pub fn from_slice(data: &[u8]) -> Result<Self, Error> {
        LockedBuffer::from_slice(data).map(Self::from_locked)
    }

    /// 🇺🇸 Runs `f` over the secret while holding the box's lock. 🇧🇷 Roda `f` sobre o segredo segurando o lock da caixa.
    pub fn with_bytes<T>(&self, f: impl FnOnce(&[u8]) -> T) -> Result<T, Error> {
        let guard = self.inner.lock()?;
        guard.with_bytes(f)
    }

    /// 🇺🇸 A zeroizing heap copy — for the brief moments a second operand is needed alongside another lock.
    /// 🇧🇷 Uma cópia no heap que se zera — para os breves momentos em que um segundo operando é preciso junto de outro lock.
    pub fn to_zeroizing(&self) -> Result<Zeroizing<Vec<u8>>, Error> {
        self.with_bytes(|bytes| Zeroizing::new(bytes.to_vec()))
    }

    fn pickle_refused() -> PyErr {
        PyTypeError::new_err(
            "SecretBox cannot be pickled, copied or deep-copied; use clone() deliberately · \
             SecretBox não pode ser serializado, copiado ou deep-copiado; use clone() de propósito",
        )
    }
}

#[pymethods]
impl SecretBox {
    /// 🇺🇸 `length` fresh bytes from the OS CSPRNG, born directly in locked memory.
    /// 🇧🇷 `length` bytes novos do CSPRNG do SO, nascidos direto em memória travada.
    #[staticmethod]
    fn random(length: usize) -> PyResult<Self> {
        let mut buffer = LockedBuffer::new(length)?;
        buffer.with_bytes_mut(rng::fill)??;
        Ok(Self::from_locked(buffer))
    }

    /// 🇺🇸 Copies a bytes-like object in; a writable source (`bytearray`) is zeroed afterwards.
    /// 🇧🇷 Copia um objeto tipo bytes para dentro; uma origem gravável (`bytearray`) é zerada depois.
    #[staticmethod]
    fn from_bytes(data: &Bound<'_, PyAny>) -> PyResult<Self> {
        let (copy, _wiped) = take_bytes(data)?;
        Ok(Self::from_slice(&copy)?)
    }

    fn __len__(&self) -> PyResult<usize> {
        Ok(self.inner.lock().map_err(Error::from)?.len())
    }

    fn __repr__(&self) -> String {
        match self.inner.lock() {
            Ok(guard) => format!(
                "SecretBox(<{} bytes, redacted, locked={}, wiped={}>)",
                guard.len(),
                guard.is_locked(),
                guard.is_wiped()
            ),
            Err(_) => "SecretBox(<poisoned>)".to_owned(),
        }
    }

    /// 🇺🇸 Constant-time equality with another box. 🇧🇷 Igualdade em tempo constante com outra caixa.
    fn __eq__(&self, other: PyRef<'_, Self>) -> PyResult<bool> {
        if std::ptr::eq(self, &raw const *other) {
            return Ok(true);
        }
        let theirs = other.to_zeroizing()?;
        Ok(self.with_bytes(|mine| mine.len() == theirs.len() && bool::from(mine.ct_eq(&theirs)))?)
    }

    fn __reduce__(&self) -> PyResult<()> {
        Err(Self::pickle_refused())
    }

    fn __copy__(&self) -> PyResult<()> {
        Err(Self::pickle_refused())
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> PyResult<()> {
        Err(Self::pickle_refused())
    }

    /// 🇺🇸 Whether the pages are pinned by `mlock`. 🇧🇷 Se as páginas estão presas por `mlock`.
    #[getter]
    fn is_locked(&self) -> PyResult<bool> {
        Ok(self.inner.lock().map_err(Error::from)?.is_locked())
    }

    /// 🇺🇸 Whether `wipe()` already ran. 🇧🇷 Se `wipe()` já rodou.
    #[getter]
    fn is_wiped(&self) -> PyResult<bool> {
        Ok(self.inner.lock().map_err(Error::from)?.is_wiped())
    }

    /// 🇺🇸 Zeroes the secret now, ahead of garbage collection. 🇧🇷 Zera o segredo agora, antes da coleta de lixo.
    fn wipe(&self) -> PyResult<()> {
        self.inner.lock().map_err(Error::from)?.wipe();
        Ok(())
    }

    /// 🇺🇸 A second, independent box with the same bytes. 🇧🇷 Uma segunda caixa, independente, com os mesmos bytes.
    #[pyo3(name = "clone")]
    fn clone_box(&self) -> PyResult<Self> {
        let guard = self.inner.lock().map_err(Error::from)?;
        Ok(Self::from_locked(guard.duplicate()?))
    }

    /// 🇺🇸 The bytes as a `bytearray` — the caller owns zeroing it. Exists only for persisting to OpenBao.
    /// 🇧🇷 Os bytes como `bytearray` — zerá-lo é responsabilidade de quem chama. Existe só para persistir no OpenBao.
    fn reveal<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyByteArray>> {
        Ok(self.with_bytes(|bytes| PyByteArray::new(py, bytes))?)
    }

    /// 🇺🇸 HMAC-SHA512 tag of `message` under this key. 🇧🇷 Tag HMAC-SHA512 de `message` sob esta chave.
    fn hmac_sha512<'py>(&self, py: Python<'py>, message: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyBytes>> {
        let message = read_bytes(message)?;
        let tag = self.with_bytes(|key| kdf::hmac_sha512(key, &message))??;
        Ok(PyBytes::new(py, &tag))
    }

    /// 🇺🇸 HKDF-SHA256 with this box as IKM; the output is a new locked box.
    /// 🇧🇷 HKDF-SHA256 com esta caixa como IKM; a saída é uma caixa travada nova.
    #[pyo3(signature = (*, info, length = 32, salt = None))]
    fn hkdf_sha256(&self, info: &Bound<'_, PyAny>, length: usize, salt: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        let info = read_bytes(info)?;
        let salt = read_optional(salt)?;
        let mut out = LockedBuffer::new(length)?;
        self.with_bytes(|ikm| {
            out.with_bytes_mut(|okm| kdf::hkdf_sha256(ikm, salt.as_deref().map(|s| &s[..]), &info, okm))
        })???;
        Ok(Self::from_locked(out))
    }

    /// 🇺🇸 AES-256-GCM `ciphertext ‖ tag` of `plaintext` under this key. 🇧🇷 `ciphertext ‖ tag` AES-256-GCM de `plaintext` sob esta chave.
    #[pyo3(signature = (nonce, plaintext, aad = None))]
    fn aes_gcm_seal<'py>(
        &self,
        py: Python<'py>,
        nonce: &Bound<'py, PyAny>,
        plaintext: &Bound<'py, PyAny>,
        aad: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let nonce = read_bytes(nonce)?;
        let plaintext = read_bytes(plaintext)?;
        let aad = read_optional(aad)?;
        let sealed =
            self.with_bytes(|key| aead::seal(key, &nonce, &plaintext, aad.as_deref().map_or(&[][..], |a| &a[..])))??;
        Ok(PyBytes::new(py, &sealed))
    }

    /// 🇺🇸 Like `aes_gcm_seal`, but the plaintext is another box (wrapping a key). 🇧🇷 Como `aes_gcm_seal`, mas o texto claro é outra caixa (embrulhar uma chave).
    #[pyo3(signature = (nonce, secret, aad = None))]
    fn aes_gcm_seal_secret<'py>(
        &self,
        py: Python<'py>,
        nonce: &Bound<'py, PyAny>,
        secret: PyRef<'py, Self>,
        aad: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let nonce = read_bytes(nonce)?;
        let aad = read_optional(aad)?;
        let plaintext = secret.to_zeroizing()?;
        let sealed =
            self.with_bytes(|key| aead::seal(key, &nonce, &plaintext, aad.as_deref().map_or(&[][..], |a| &a[..])))??;
        Ok(PyBytes::new(py, &sealed))
    }

    /// 🇺🇸 Opens AES-256-GCM `ciphertext ‖ tag` to plain `bytes` (for content). 🇧🇷 Abre `ciphertext ‖ tag` AES-256-GCM em `bytes` (para conteúdo).
    #[pyo3(signature = (nonce, ciphertext, aad = None))]
    fn aes_gcm_open<'py>(
        &self,
        py: Python<'py>,
        nonce: &Bound<'py, PyAny>,
        ciphertext: &Bound<'py, PyAny>,
        aad: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let plaintext = self.open_zeroizing(nonce, ciphertext, aad)?;
        Ok(PyBytes::new(py, &plaintext))
    }

    /// 🇺🇸 Opens `ciphertext`, parses the plaintext as a JSON object and moves one base64url field straight into a locked box.
    ///
    /// This is how `X-Session-Seed` (`docs/PROTOCOL.md §4`, `{"seed": "<b64url>"}`)
    /// is consumed: the JSON and the encoded seed exist only in zeroizing Rust
    /// memory, never in the Python heap.
    ///
    /// 🇧🇷 Abre `ciphertext`, interpreta o texto claro como objeto JSON e move um campo base64url direto para uma caixa travada.
    ///
    /// É assim que `X-Session-Seed` (`docs/PROTOCOL.md §4`, `{"seed": "<b64url>"}`)
    /// é consumido: o JSON e a semente codificada existem só em memória Rust
    /// que se zera, nunca no heap do Python.
    #[pyo3(signature = (nonce, ciphertext, aad, field))]
    fn aes_gcm_open_json_field(
        &self,
        nonce: &Bound<'_, PyAny>,
        ciphertext: &Bound<'_, PyAny>,
        aad: Option<&Bound<'_, PyAny>>,
        field: &str,
    ) -> PyResult<Self> {
        let plaintext = self.open_zeroizing(nonce, ciphertext, aad)?;
        let object: serde_json::Map<String, serde_json::Value> =
            serde_json::from_slice(&plaintext).map_err(|_| Error::Malformed("json object"))?;
        let value = object.get(field).and_then(serde_json::Value::as_str).ok_or(Error::Malformed("json field"))?;
        let decoded = b64url_decode(value)?;
        Ok(Self::from_slice(&decoded)?)
    }

    /// 🇺🇸 Opens into a new locked box (for keys). 🇧🇷 Abre para uma caixa travada nova (para chaves).
    #[pyo3(signature = (nonce, ciphertext, aad = None))]
    fn aes_gcm_open_secret(
        &self,
        nonce: &Bound<'_, PyAny>,
        ciphertext: &Bound<'_, PyAny>,
        aad: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let plaintext = self.open_zeroizing(nonce, ciphertext, aad)?;
        Ok(Self::from_slice(&plaintext)?)
    }
}

impl SecretBox {
    fn open_zeroizing(
        &self,
        nonce: &Bound<'_, PyAny>,
        ciphertext: &Bound<'_, PyAny>,
        aad: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Zeroizing<Vec<u8>>> {
        let nonce = read_bytes(nonce)?;
        let ciphertext = read_bytes(ciphertext)?;
        let aad = read_optional(aad)?;
        Ok(self.with_bytes(|key| aead::open(key, &nonce, &ciphertext, aad.as_deref().map_or(&[][..], |a| &a[..])))??)
    }
}
