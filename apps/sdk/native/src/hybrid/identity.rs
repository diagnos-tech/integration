//! 🇺🇸 The identity's private halves, kept in locked buffers and expanded only for the moment an `open` takes.
//!
//! 🇧🇷 As metades privadas da identidade, em buffers travados e expandidas só pelo instante de um `open`.

use ml_kem::kem::{Decapsulate, Kem};
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
#[allow(deprecated)]
use ml_kem::ExpandedKeyEncoding;
use ml_kem::{DecapsulationKey, KeyExport, MlKem768};
use x25519_dalek::{PublicKey, StaticSecret};
use zeroize::Zeroizing;

use super::{derive_key, ENCAPSULATION_BYTES, MLKEM768_SECRET_BYTES, X25519_PUBLIC_BYTES, X25519_SECRET_BYTES};
use crate::error::{expect_len, Error};
use crate::locked::LockedBuffer;
use crate::{aead, rng};

/// 🇺🇸 The Rust-level identity behind [`HybridKeyPair`](super::HybridKeyPair); public for the crate's own tests and vectors.
/// 🇧🇷 A identidade em nível Rust por trás de [`HybridKeyPair`](super::HybridKeyPair); pública para os testes e vetores do próprio crate.
pub struct Identity {
    pub(super) x25519_secret: LockedBuffer,
    pub(super) mlkem768_secret: LockedBuffer,
    pub(super) x25519_public: [u8; X25519_PUBLIC_BYTES],
    pub(super) mlkem768_public: Vec<u8>,
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hybrid::seal;

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
