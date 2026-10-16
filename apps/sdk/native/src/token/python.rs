//! 🇺🇸 What Python sees of the token: `TokenKeys`, `decode_token`, `encode_token` and `verify_token_signature`.
//!
//! 🇧🇷 O que o Python enxerga do token: `TokenKeys`, `decode_token`, `encode_token` e `verify_token_signature`.

use std::sync::Mutex;

use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use super::codec::{self, KEY_ID_BYTES};
use super::keys::{self, Keys};
use crate::buffer::read_bytes;
use crate::error::Error;
use crate::hybrid::HybridKeyPair;
use crate::secret_box::SecretBox;

/// 🇺🇸 The keys of one token: built from its seed, used here, never exported.
/// 🇧🇷 As chaves de um token: construídas da semente, usadas aqui, nunca exportadas.
#[pyclass(frozen, name = "TokenKeys", module = "diagnos._secure")]
pub struct TokenKeys {
    inner: Mutex<Keys>,
}

impl TokenKeys {
    fn with_keys<T>(&self, f: impl FnOnce(&Keys) -> Result<T, Error>) -> PyResult<T> {
        let guard = self.inner.lock().map_err(Error::from)?;
        Ok(f(&guard)?)
    }

    fn refused() -> PyErr {
        PyTypeError::new_err("TokenKeys cannot be pickled or copied · TokenKeys não pode ser serializado nem copiado")
    }
}

#[pymethods]
impl TokenKeys {
    /// 🇺🇸 Derives the four key pairs from the 32-byte seed in `seed` (spec §3).
    /// 🇧🇷 Deriva os quatro pares a partir da semente de 32 bytes em `seed` (spec §3).
    #[staticmethod]
    fn from_seed(seed: PyRef<'_, SecretBox>) -> PyResult<Self> {
        let keys = seed.with_bytes(Keys::from_seed)??;
        Ok(Self { inner: Mutex::new(keys) })
    }

    /// 🇺🇸 32-byte Ed25519 public key. 🇧🇷 Chave pública Ed25519 de 32 bytes.
    #[getter]
    fn ed25519_public<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        self.with_keys(|keys| Ok(PyBytes::new(py, keys.ed25519_public())))
    }

    /// 🇺🇸 1952-byte ML-DSA-65 public key. 🇧🇷 Chave pública ML-DSA-65 de 1952 bytes.
    #[getter]
    fn mldsa65_public<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        self.with_keys(|keys| Ok(PyBytes::new(py, keys.mldsa65_public())))
    }

    /// 🇺🇸 32-byte X25519 public key. 🇧🇷 Chave pública X25519 de 32 bytes.
    #[getter]
    fn x25519_public<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        self.with_keys(|keys| Ok(PyBytes::new(py, keys.kem().x25519_public())))
    }

    /// 🇺🇸 1184-byte ML-KEM-768 encapsulation key. 🇧🇷 Chave de encapsulamento ML-KEM-768 de 1184 bytes.
    #[getter]
    fn mlkem768_public<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        self.with_keys(|keys| Ok(PyBytes::new(py, keys.kem().mlkem768_public())))
    }

    /// 🇺🇸 The 3373-byte hybrid signature of `message` (spec §4); `deterministic=True` only reproduces vectors.
    /// 🇧🇷 A assinatura híbrida de 3373 bytes de `message` (spec §4); `deterministic=True` só reproduz vetores.
    #[pyo3(signature = (message, *, deterministic = false))]
    fn sign<'py>(
        &self,
        py: Python<'py>,
        message: &Bound<'py, PyAny>,
        deterministic: bool,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let message = read_bytes(message)?;
        let signature = self.with_keys(|keys| keys.sign(&message, deterministic))?;
        Ok(PyBytes::new(py, &signature))
    }

    /// 🇺🇸 A `HybridKeyPair` with its own locked copy of the seal pair — the session layer opens with it and wipes it.
    /// 🇧🇷 Um `HybridKeyPair` com cópia travada própria do par de selo — a camada de sessão abre com ele e o apaga.
    fn hybrid_keypair(&self) -> PyResult<HybridKeyPair> {
        self.with_keys(|keys| keys.kem().duplicate().map(HybridKeyPair::from_identity))
    }

    /// 🇺🇸 Zeroes every private half now. 🇧🇷 Zera toda metade privada agora.
    fn wipe(&self) -> PyResult<()> {
        self.inner.lock().map_err(Error::from)?.wipe();
        Ok(())
    }

    /// 🇺🇸 Whether `wipe()` already ran. 🇧🇷 Se `wipe()` já rodou.
    #[getter]
    fn is_wiped(&self) -> PyResult<bool> {
        self.with_keys(|keys| Ok(keys.is_wiped()))
    }

    fn __repr__(&self) -> String {
        "TokenKeys(<ed25519 + ml-dsa-65 + x25519 + ml-kem-768, secrets redacted>)".to_owned()
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

/// 🇺🇸 `decode_token(text) -> (key_id, seed, workspace_id)`; a `ValueError` whose only argument is the failure code.
/// 🇧🇷 `decode_token(text) -> (key_id, seed, workspace_id)`; um `ValueError` cujo único argumento é o código da falha.
#[pyfunction]
pub fn decode_token<'py>(py: Python<'py>, text: &str) -> PyResult<(Bound<'py, PyBytes>, SecretBox, String)> {
    let decoded = codec::decode(text).map_err(|error| PyValueError::new_err(error.code()))?;
    let seed = SecretBox::from_slice(&decoded.seed[..])?;
    Ok((PyBytes::new(py, &decoded.key_id), seed, decoded.workspace_id))
}

/// 🇺🇸 `encode_token(key_id, seed, workspace_id) -> str` — tests and tooling; real tokens are minted in the browser.
/// 🇧🇷 `encode_token(key_id, seed, workspace_id) -> str` — testes e ferramentas; tokens reais nascem no navegador.
#[pyfunction]
pub fn encode_token(key_id: &Bound<'_, PyAny>, seed: PyRef<'_, SecretBox>, workspace_id: &str) -> PyResult<String> {
    let key_id = read_bytes(key_id)?;
    if key_id.len() != KEY_ID_BYTES {
        return Err(PyValueError::new_err(codec::TokenError::Length.code()));
    }
    let text = seed
        .with_bytes(|bytes| codec::encode(&key_id, bytes, workspace_id))?
        .map_err(|error| PyValueError::new_err(error.code()))?;
    Ok(text.to_string())
}

/// 🇺🇸 Whether `signature` is a valid hybrid signature of `message` — what the vault checks; for tests and doubles.
/// 🇧🇷 Se `signature` é uma assinatura híbrida válida de `message` — o que o cofre confere; para testes e dublês.
#[pyfunction]
pub fn verify_token_signature(
    ed25519_public: &Bound<'_, PyAny>,
    mldsa65_public: &Bound<'_, PyAny>,
    message: &Bound<'_, PyAny>,
    signature: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    Ok(keys::verify(
        &read_bytes(ed25519_public)?,
        &read_bytes(mldsa65_public)?,
        &read_bytes(message)?,
        &read_bytes(signature)?,
    ))
}
