//! 🇺🇸 What Python sees of the hybrid seal: the `HybridKeyPair` class and `seal_hybrid`.
//!
//! 🇧🇷 O que o Python enxerga do selo híbrido: a classe `HybridKeyPair` e o `seal_hybrid`.

use std::sync::Mutex;

use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use serde::Deserialize;
use zeroize::Zeroizing;

use super::{seal, Identity};
use crate::aead;
use crate::buffer::read_bytes;
use crate::error::{expect_len, Error};
use crate::secret_box::SecretBox;

/// 🇺🇸 The JSON a sealed session opens to (`docs/PROTOCOL.md §5`); key strings zeroize on drop.
/// 🇧🇷 O JSON para o qual uma sessão selada abre (`docs/PROTOCOL.md §5`); as strings de chave se zeram ao descartar.
#[derive(Deserialize)]
struct SealedSession {
    session_id: String,
    sign_key: Zeroizing<String>,
    enc_key: Zeroizing<String>,
    expires_at: i64,
}

/// 🇺🇸 base64url (padding optional) into zeroizing memory. 🇧🇷 base64url (padding opcional) em memória que se zera.
pub fn b64url_decode(text: &str) -> Result<Zeroizing<Vec<u8>>, Error> {
    use base64::Engine as _;
    let trimmed = text.trim_end_matches('=');
    base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(trimmed)
        .map(Zeroizing::new)
        .map_err(|_| Error::Malformed("base64url"))
}

/// 🇺🇸 An SDK identity: one X25519 pair plus one ML-KEM-768 pair, private halves in locked memory.
/// 🇧🇷 Uma identidade de SDK: um par X25519 mais um par ML-KEM-768, metades privadas em memória travada.
#[pyclass(frozen, name = "HybridKeyPair", module = "diagnos._secure")]
pub struct HybridKeyPair {
    inner: Mutex<Identity>,
}

impl HybridKeyPair {
    fn with_identity<T>(&self, f: impl FnOnce(&Identity) -> Result<T, Error>) -> PyResult<T> {
        let guard = self.inner.lock().map_err(Error::from)?;
        Ok(f(&guard)?)
    }

    fn refused() -> PyErr {
        PyTypeError::new_err(
            "HybridKeyPair cannot be pickled or copied · HybridKeyPair não pode ser serializado nem copiado",
        )
    }
}

#[pymethods]
impl HybridKeyPair {
    /// 🇺🇸 A fresh identity from the OS CSPRNG. 🇧🇷 Uma identidade nova do CSPRNG do SO.
    #[staticmethod]
    fn generate() -> PyResult<Self> {
        Ok(Self { inner: Mutex::new(Identity::generate()?) })
    }

    /// 🇺🇸 Rebuilds an identity from its two secrets (an OpenBao restore); publics are recomputed, never trusted from storage.
    /// 🇧🇷 Reconstrói uma identidade das duas secretas (restore do OpenBao); as públicas são recalculadas, nunca confiadas do armazenamento.
    #[staticmethod]
    fn from_secrets(x25519_secret: PyRef<'_, SecretBox>, mlkem768_secret: PyRef<'_, SecretBox>) -> PyResult<Self> {
        let x = x25519_secret.to_zeroizing()?;
        let k = mlkem768_secret.to_zeroizing()?;
        Ok(Self { inner: Mutex::new(Identity::from_secrets(&x, &k)?) })
    }

    /// 🇺🇸 32-byte X25519 public key. 🇧🇷 Chave pública X25519 de 32 bytes.
    #[getter]
    fn x25519_public<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        self.with_identity(|id| Ok(PyBytes::new(py, &id.x25519_public)))
    }

    /// 🇺🇸 1184-byte ML-KEM-768 encapsulation key. 🇧🇷 Chave de encapsulamento ML-KEM-768 de 1184 bytes.
    #[getter]
    fn mlkem768_public<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        self.with_identity(|id| Ok(PyBytes::new(py, &id.mlkem768_public)))
    }

    /// 🇺🇸 A locked copy of the X25519 secret, for persisting. 🇧🇷 Uma cópia travada da secreta X25519, para persistir.
    fn x25519_secret(&self) -> PyResult<SecretBox> {
        self.with_identity(|id| id.x25519_secret.duplicate().map(SecretBox::from_locked))
    }

    /// 🇺🇸 A locked copy of the expanded ML-KEM-768 secret, for persisting. 🇧🇷 Uma cópia travada da secreta ML-KEM-768 expandida, para persistir.
    fn mlkem768_secret(&self) -> PyResult<SecretBox> {
        self.with_identity(|id| id.mlkem768_secret.duplicate().map(SecretBox::from_locked))
    }

    /// 🇺🇸 Opens a seal to plain `bytes` (JSON, content). 🇧🇷 Abre um selo para `bytes` (JSON, conteúdo).
    fn open<'py>(
        &self,
        py: Python<'py>,
        encapsulation: &Bound<'py, PyAny>,
        nonce: &Bound<'py, PyAny>,
        ciphertext: &Bound<'py, PyAny>,
        aad: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let plaintext = self.open_zeroizing(encapsulation, nonce, ciphertext, aad)?;
        Ok(PyBytes::new(py, &plaintext))
    }

    /// 🇺🇸 Opens a seal straight into a locked box (a group DEK). 🇧🇷 Abre um selo direto numa caixa travada (uma DEK de grupo).
    fn open_secret(
        &self,
        encapsulation: &Bound<'_, PyAny>,
        nonce: &Bound<'_, PyAny>,
        ciphertext: &Bound<'_, PyAny>,
        aad: &Bound<'_, PyAny>,
    ) -> PyResult<SecretBox> {
        let plaintext = self.open_zeroizing(encapsulation, nonce, ciphertext, aad)?;
        Ok(SecretBox::from_slice(&plaintext)?)
    }

    /// 🇺🇸 Opens a sealed session (`docs/PROTOCOL.md §5`) as `(session_id, expires_at, sign_key, enc_key)` with both keys locked.
    /// 🇧🇷 Abre uma sessão selada (`docs/PROTOCOL.md §5`) como `(session_id, expires_at, sign_key, enc_key)` com as duas chaves travadas.
    fn open_session(
        &self,
        encapsulation: &Bound<'_, PyAny>,
        nonce: &Bound<'_, PyAny>,
        ciphertext: &Bound<'_, PyAny>,
        aad: &Bound<'_, PyAny>,
    ) -> PyResult<(String, i64, SecretBox, SecretBox)> {
        let plaintext = self.open_zeroizing(encapsulation, nonce, ciphertext, aad)?;
        let session: SealedSession =
            serde_json::from_slice(&plaintext).map_err(|_| Error::Malformed("sealed session"))?;
        let sign_key = b64url_decode(&session.sign_key)?;
        let enc_key = b64url_decode(&session.enc_key)?;
        expect_len("sign_key", &sign_key, aead::KEY_BYTES)?;
        expect_len("enc_key", &enc_key, aead::KEY_BYTES)?;
        Ok((
            session.session_id,
            session.expires_at,
            SecretBox::from_slice(&sign_key)?,
            SecretBox::from_slice(&enc_key)?,
        ))
    }

    /// 🇺🇸 Zeroes both secrets now. 🇧🇷 Zera as duas secretas agora.
    fn wipe(&self) -> PyResult<()> {
        let mut guard = self.inner.lock().map_err(Error::from)?;
        guard.x25519_secret.wipe();
        guard.mlkem768_secret.wipe();
        Ok(())
    }

    /// 🇺🇸 Whether `wipe()` already ran. 🇧🇷 Se `wipe()` já rodou.
    #[getter]
    fn is_wiped(&self) -> PyResult<bool> {
        self.with_identity(|id| Ok(id.x25519_secret.is_wiped()))
    }

    fn __repr__(&self) -> String {
        "HybridKeyPair(<x25519 + ml-kem-768, secrets redacted>)".to_owned()
    }

    fn __reduce__(&self) -> PyResult<()> {
        Err(Self::refused())
    }

    fn __copy__(&self) -> PyResult<()> {
        Err(Self::refused())
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> PyResult<()> {
        Err(Self::refused())
    }
}

impl HybridKeyPair {
    fn open_zeroizing(
        &self,
        encapsulation: &Bound<'_, PyAny>,
        nonce: &Bound<'_, PyAny>,
        ciphertext: &Bound<'_, PyAny>,
        aad: &Bound<'_, PyAny>,
    ) -> PyResult<Zeroizing<Vec<u8>>> {
        let encapsulation = read_bytes(encapsulation)?;
        let nonce = read_bytes(nonce)?;
        let ciphertext = read_bytes(ciphertext)?;
        let aad = read_bytes(aad)?;
        self.with_identity(|id| id.open(&encapsulation, &nonce, &ciphertext, &aad))
    }
}

/// 🇺🇸 `seal_hybrid(x25519_public, mlkem768_public, plaintext, aad) -> (encapsulation, nonce, ciphertext)`.
/// 🇧🇷 `seal_hybrid(x25519_public, mlkem768_public, plaintext, aad) -> (encapsulation, nonce, ciphertext)`.
#[pyfunction]
pub fn seal_hybrid<'py>(
    py: Python<'py>,
    x25519_public: &Bound<'py, PyAny>,
    mlkem768_public: &Bound<'py, PyAny>,
    plaintext: &Bound<'py, PyAny>,
    aad: &Bound<'py, PyAny>,
) -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>)> {
    let x = read_bytes(x25519_public)?;
    let k = read_bytes(mlkem768_public)?;
    let plaintext = read_bytes(plaintext)?;
    let aad = read_bytes(aad)?;
    let sealed = seal(&x, &k, &plaintext, &aad)?;
    Ok((PyBytes::new(py, &sealed.encapsulation), PyBytes::new(py, &sealed.nonce), PyBytes::new(py, &sealed.ciphertext)))
}
