//! 🇺🇸 HybridSeal — X25519 + ML-KEM-768 → HKDF-SHA256 → AES-256-GCM (`docs/PROTOCOL.md §6`).
//!
//! The SDK's identity is a [`HybridKeyPair`]. Its two private halves are the
//! most valuable bytes in the process: they open every session and every
//! group DEK the vault or the web app ever seals to it. They are stored as
//! raw encodings in two locked buffers and only expanded into working key
//! objects — on the stack/heap, zeroized on drop — for the microseconds an
//! `open` takes. Public halves are plain `Vec`s: they are meant to be shown.
//!
//! Wire format (`EncryptedPayload`): `salt = eph_pub ‖ kem_ct` (1120 B),
//! `nonce` (12 B), `ciphertext ‖ tag`; `key = HKDF(ss1 ‖ ss2, salt = ∅,
//! info = "imgexam-sdk-hybrid-seal-v1" ‖ salt)`. Reference:
//! the vault's `hybridSeal`, pinned by `apps/sdk/tests/vectors/hybrid_seal.json`.
//!
//! 🇧🇷 HybridSeal — X25519 + ML-KEM-768 → HKDF-SHA256 → AES-256-GCM (`docs/PROTOCOL.md §6`).
//!
//! A identidade do SDK é um [`HybridKeyPair`]. Suas duas metades privadas são
//! os bytes mais valiosos do processo: abrem toda sessão e toda DEK de grupo
//! que o cofre ou o app web algum dia selar para ele. Ficam guardadas como
//! codificações cruas em dois buffers travados e só são expandidas em objetos
//! de chave de trabalho — na pilha/heap, zerados ao descartar — pelos
//! microssegundos que um `open` leva. As metades públicas são `Vec`s comuns:
//! existem para serem mostradas.
//!
//! Formato de fio (`EncryptedPayload`): `salt = eph_pub ‖ kem_ct` (1120 B),
//! `nonce` (12 B), `ciphertext ‖ tag`; `key = HKDF(ss1 ‖ ss2, salt = ∅,
//! info = "imgexam-sdk-hybrid-seal-v1" ‖ salt)`.

use std::sync::Mutex;

// 🇺🇸 `ExpandedKeyEncoding` is deprecated upstream in favour of 64-byte seeds,
//    but the protocol (`docs/PROTOCOL.md §6, §11`) fixes the FIPS 203 *expanded*
//    encoding — it is what `@noble/post-quantum` and `kyber-py` emit, what the
//    vectors carry and what OpenBao stores. Interoperability wins over the
//    upstream preference; the seed form would be a wire-format change.
// 🇧🇷 `ExpandedKeyEncoding` está deprecado upstream em favor de seeds de 64
//    bytes, mas o protocolo (`docs/PROTOCOL.md §6, §11`) fixa a codificação
//    *expandida* da FIPS 203 — é o que `@noble/post-quantum` e `kyber-py`
//    emitem, o que os vetores carregam e o que o OpenBao guarda.
//    Interoperabilidade vence a preferência upstream; a forma de seed seria
//    uma mudança de formato de fio.
use ml_kem::kem::{Decapsulate, Encapsulate, Kem};
#[allow(deprecated)]
use ml_kem::ExpandedKeyEncoding;
use ml_kem::{DecapsulationKey, EncapsulationKey, KeyExport, MlKem768};
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use serde::Deserialize;
use x25519_dalek::{EphemeralSecret, PublicKey, StaticSecret};
use zeroize::Zeroizing;

use crate::buffer::read_bytes;
use crate::error::{expect_len, Error};
use crate::locked::LockedBuffer;
use crate::secret_box::SecretBox;
use crate::{aead, kdf, rng};

/// 🇺🇸 X25519 public key length. 🇧🇷 Tamanho da chave pública X25519.
pub const X25519_PUBLIC_BYTES: usize = 32;
/// 🇺🇸 X25519 secret key length. 🇧🇷 Tamanho da chave secreta X25519.
pub const X25519_SECRET_BYTES: usize = 32;
/// 🇺🇸 ML-KEM-768 encapsulation key length (FIPS 203). 🇧🇷 Tamanho da chave de encapsulamento ML-KEM-768 (FIPS 203).
pub const MLKEM768_PUBLIC_BYTES: usize = 1184;
/// 🇺🇸 ML-KEM-768 expanded decapsulation key length: `dk_pke ‖ ek ‖ H(ek) ‖ z`. 🇧🇷 Tamanho da chave de decapsulamento expandida ML-KEM-768.
pub const MLKEM768_SECRET_BYTES: usize = 2400;
/// 🇺🇸 ML-KEM-768 ciphertext length. 🇧🇷 Tamanho do ciphertext ML-KEM-768.
pub const MLKEM768_CIPHERTEXT_BYTES: usize = 1088;
/// 🇺🇸 `eph_pub ‖ kem_ct`. 🇧🇷 `eph_pub ‖ kem_ct`.
pub const ENCAPSULATION_BYTES: usize = X25519_PUBLIC_BYTES + MLKEM768_CIPHERTEXT_BYTES;
/// 🇺🇸 HKDF `info` prefix of the seal — a frozen wire constant; the `imgexam-` prefix is historical.
/// 🇧🇷 Prefixo de `info` do HKDF do selo — constante de fio congelada; o prefixo `imgexam-` é histórico.
pub const INFO: &[u8] = b"imgexam-sdk-hybrid-seal-v1";

/// 🇺🇸 The three wire fields of a seal, still raw bytes. 🇧🇷 Os três campos de fio de um selo, ainda em bytes crus.
pub struct Sealed {
    /// 🇺🇸 `eph_pub ‖ kem_ct`. 🇧🇷 `eph_pub ‖ kem_ct`.
    pub encapsulation: Vec<u8>,
    /// 🇺🇸 12 random bytes. 🇧🇷 12 bytes aleatórios.
    pub nonce: [u8; aead::NONCE_BYTES],
    /// 🇺🇸 `ciphertext ‖ tag`. 🇧🇷 `ciphertext ‖ tag`.
    pub ciphertext: Vec<u8>,
}

fn derive_key(ss1: &[u8], ss2: &[u8], encapsulation: &[u8]) -> Result<Zeroizing<[u8; aead::KEY_BYTES]>, Error> {
    let mut ikm = Zeroizing::new(Vec::with_capacity(ss1.len() + ss2.len()));
    ikm.extend_from_slice(ss1);
    ikm.extend_from_slice(ss2);
    let mut info = Vec::with_capacity(INFO.len() + encapsulation.len());
    info.extend_from_slice(INFO);
    info.extend_from_slice(encapsulation);
    let mut key = Zeroizing::new([0u8; aead::KEY_BYTES]);
    kdf::hkdf_sha256(&ikm, None, &info, &mut key[..])?;
    Ok(key)
}

/// 🇺🇸 Seals `plaintext` to a recipient's public keys; `aad` binds it to the enrollment.
/// 🇧🇷 Sela `plaintext` para as chaves públicas de um destinatário; `aad` o amarra ao enrollment.
pub fn seal(x25519_public: &[u8], mlkem768_public: &[u8], plaintext: &[u8], aad: &[u8]) -> Result<Sealed, Error> {
    expect_len("x25519 public key", x25519_public, X25519_PUBLIC_BYTES)?;
    expect_len("ml-kem-768 public key", mlkem768_public, MLKEM768_PUBLIC_BYTES)?;
    let mut recipient = [0u8; X25519_PUBLIC_BYTES];
    recipient.copy_from_slice(x25519_public);

    let mut csprng = rng::csprng();
    let eph = EphemeralSecret::random_from_rng(&mut csprng);
    let eph_public = PublicKey::from(&eph);
    let ss1 = eph.diffie_hellman(&PublicKey::from(recipient));
    if !ss1.was_contributory() {
        return Err(Error::InvalidKey);
    }

    let ek = EncapsulationKey::<MlKem768>::new(mlkem768_public.try_into().map_err(|_| Error::InvalidKey)?)
        .map_err(|_| Error::InvalidKey)?;
    let (kem_ct, ss2) = ek.encapsulate_with_rng(&mut csprng);

    let mut encapsulation = Vec::with_capacity(ENCAPSULATION_BYTES);
    encapsulation.extend_from_slice(eph_public.as_bytes());
    encapsulation.extend_from_slice(kem_ct.as_ref());
    let key = derive_key(ss1.as_bytes(), ss2.as_ref(), &encapsulation)?;
    let nonce = rng::random_array::<{ aead::NONCE_BYTES }>()?;
    let ciphertext = aead::seal(&key[..], &nonce, plaintext, aad)?;
    Ok(Sealed { encapsulation, nonce, ciphertext })
}

/// 🇺🇸 The Rust-level identity behind [`HybridKeyPair`]; public for the crate's own tests and vectors.
/// 🇧🇷 A identidade em nível Rust por trás de [`HybridKeyPair`]; pública para os testes e vetores do próprio crate.
pub struct Identity {
    x25519_secret: LockedBuffer,
    mlkem768_secret: LockedBuffer,
    x25519_public: [u8; X25519_PUBLIC_BYTES],
    mlkem768_public: Vec<u8>,
}

#[allow(deprecated)]
impl Identity {
    /// 🇺🇸 Rebuilds an identity from raw secret encodings (32 B X25519, 2400 B ML-KEM-768 expanded).
    /// 🇧🇷 Reconstrói uma identidade das codificações secretas cruas (32 B X25519, 2400 B ML-KEM-768 expandida).
    pub fn from_secrets(x25519_secret: &[u8], mlkem768_secret: &[u8]) -> Result<Self, Error> {
        expect_len("x25519 secret key", x25519_secret, X25519_SECRET_BYTES)?;
        expect_len("ml-kem-768 secret key", mlkem768_secret, MLKEM768_SECRET_BYTES)?;
        let mut seed = Zeroizing::new([0u8; X25519_SECRET_BYTES]);
        seed.copy_from_slice(x25519_secret);
        let x25519_public = PublicKey::from(&StaticSecret::from(*seed)).to_bytes();
        let dk = DecapsulationKey::<MlKem768>::from_expanded_bytes(
            mlkem768_secret.try_into().map_err(|_| Error::InvalidKey)?,
        )
        .map_err(|_| Error::InvalidKey)?;
        let mlkem768_public = dk.encapsulation_key().to_bytes().to_vec();
        Ok(Self {
            x25519_secret: LockedBuffer::from_slice(x25519_secret)?,
            mlkem768_secret: LockedBuffer::from_slice(mlkem768_secret)?,
            x25519_public,
            mlkem768_public,
        })
    }

    /// 🇺🇸 A fresh identity from the OS CSPRNG. 🇧🇷 Uma identidade nova do CSPRNG do SO.
    pub fn generate() -> Result<Self, Error> {
        let mut csprng = rng::csprng();
        let x25519 = StaticSecret::random_from_rng(&mut csprng);
        let (dk, _ek) = MlKem768::generate_keypair_from_rng(&mut csprng);
        let x25519_bytes = Zeroizing::new(x25519.to_bytes());
        let dk_bytes = Zeroizing::new(dk.to_expanded_bytes());
        Self::from_secrets(&x25519_bytes[..], dk_bytes.as_ref())
    }

    /// 🇺🇸 X25519 public key. 🇧🇷 Chave pública X25519.
    #[must_use]
    pub fn x25519_public(&self) -> &[u8; X25519_PUBLIC_BYTES] {
        &self.x25519_public
    }

    /// 🇺🇸 ML-KEM-768 encapsulation key. 🇧🇷 Chave de encapsulamento ML-KEM-768.
    #[must_use]
    pub fn mlkem768_public(&self) -> &[u8] {
        &self.mlkem768_public
    }

    /// 🇺🇸 Opens a seal addressed to this identity. 🇧🇷 Abre um selo endereçado a esta identidade.
    pub fn open(
        &self,
        encapsulation: &[u8],
        nonce: &[u8],
        ciphertext: &[u8],
        aad: &[u8],
    ) -> Result<Zeroizing<Vec<u8>>, Error> {
        expect_len("encapsulation", encapsulation, ENCAPSULATION_BYTES)?;
        let (eph_public, kem_ct) = encapsulation.split_at(X25519_PUBLIC_BYTES);
        let mut eph = [0u8; X25519_PUBLIC_BYTES];
        eph.copy_from_slice(eph_public);

        let ss1 = self.x25519_secret.with_bytes(|secret| {
            let mut seed = Zeroizing::new([0u8; X25519_SECRET_BYTES]);
            seed.copy_from_slice(secret);
            StaticSecret::from(*seed).diffie_hellman(&PublicKey::from(eph))
        })?;
        if !ss1.was_contributory() {
            return Err(Error::DidNotOpen);
        }
        let ss2 = self.mlkem768_secret.with_bytes(|secret| {
            let dk =
                DecapsulationKey::<MlKem768>::from_expanded_bytes(secret.try_into().map_err(|_| Error::InvalidKey)?)
                    .map_err(|_| Error::InvalidKey)?;
            dk.decapsulate_slice(kem_ct).map_err(|_| Error::DidNotOpen)
        })??;

        let key = derive_key(ss1.as_bytes(), ss2.as_ref(), encapsulation)?;
        aead::open(&key[..], nonce, ciphertext, aad)
    }
}

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generate_seal_open_roundtrip() {
        let id = Identity::generate().unwrap();
        let sealed = seal(&id.x25519_public, &id.mlkem768_public, b"hello", b"enr-1").unwrap();
        assert_eq!(sealed.encapsulation.len(), ENCAPSULATION_BYTES);
        let opened = id.open(&sealed.encapsulation, &sealed.nonce, &sealed.ciphertext, b"enr-1").unwrap();
        assert_eq!(&*opened, b"hello");
        assert_eq!(
            id.open(&sealed.encapsulation, &sealed.nonce, &sealed.ciphertext, b"enr-2").unwrap_err(),
            Error::DidNotOpen
        );
    }

    #[test]
    fn from_secrets_recomputes_publics() {
        let id = Identity::generate().unwrap();
        let x = id.x25519_secret.with_bytes(<[u8]>::to_vec).unwrap();
        let k = id.mlkem768_secret.with_bytes(<[u8]>::to_vec).unwrap();
        let rebuilt = Identity::from_secrets(&x, &k).unwrap();
        assert_eq!(rebuilt.x25519_public, id.x25519_public);
        assert_eq!(rebuilt.mlkem768_public, id.mlkem768_public);
        assert_eq!(&k[1152..2336], &id.mlkem768_public[..]);
    }
}
