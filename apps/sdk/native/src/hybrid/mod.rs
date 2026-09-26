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
//!
//! Layout: this file holds the wire constants and the sealing side;
//! `identity` the private halves and `open`; `python` the
//! `HybridKeyPair` class and `seal_hybrid` that Python sees.
//!
//! 🇧🇷 Organização: este arquivo guarda as constantes de fio e o lado que sela;
//! `identity` as metades privadas e o `open`; `python` a classe
//! `HybridKeyPair` e o `seal_hybrid` que o Python enxerga.

mod identity;
mod python;

pub use identity::Identity;
pub use python::{b64url_decode, seal_hybrid, HybridKeyPair};

use ml_kem::kem::Encapsulate;
use ml_kem::{EncapsulationKey, MlKem768};
use x25519_dalek::{EphemeralSecret, PublicKey};
use zeroize::Zeroizing;

use crate::error::{expect_len, Error};
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

/// 🇺🇸 HKDF over both shared secrets, bound to the encapsulation. 🇧🇷 HKDF sobre os dois segredos, amarrado ao encapsulamento.
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
