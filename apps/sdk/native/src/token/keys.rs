//! 🇺🇸 The four key pairs a token seed derives (spec §3), and the hybrid request signature (spec §4).
//!
//! Each private key is `HKDF-SHA-256(seed, salt = "diagnos-sa-token-v1",
//! info = label)`: Ed25519 and ML-DSA-65 sign, X25519 and ML-KEM-768 open
//! the seals the vault and the browser address to the token. The four
//! secrets live in locked pages for as long as the token does; each working
//! key object (an expanded ML-DSA key is ~4 KB) exists only for the call that
//! needs it and zeroizes on drop. Only public keys and signatures leave.
//!
//! The signature is `ed25519(64) ‖ ml-dsa-65(3309)` over the same message.
//! ML-DSA runs in pure mode with the FIPS 204 context
//! `"diagnos-sa-request-v1"` (domain separation: a signature made here can
//! never be replayed as one for another protocol that uses the same key).
//! Requests use the hedged variant — 32 fresh random bytes mixed in, which
//! resists fault and side-channel attacks better, as the TypeScript
//! reference does — and `deterministic` (`rnd` = 32 zero bytes) exists so
//! the normative vectors can pin every byte. The vault accepts both and
//! requires both halves.
//!
//! 🇧🇷 Os quatro pares de chaves que a semente do token deriva (spec §3), e a assinatura híbrida (spec §4).
//!
//! Cada chave privada é `HKDF-SHA-256(seed, salt = "diagnos-sa-token-v1",
//! info = rótulo)`: Ed25519 e ML-DSA-65 assinam, X25519 e ML-KEM-768 abrem os
//! selos que o cofre e o navegador endereçam ao token. Os quatro segredos
//! vivem em páginas travadas enquanto o token viver; cada objeto de chave de
//! trabalho (uma chave ML-DSA expandida tem ~4 KB) existe só pela chamada que
//! precisa dele e se zera ao descartar. Só chaves públicas e assinaturas saem.
//!
//! A assinatura é `ed25519(64) ‖ ml-dsa-65(3309)` sobre a mesma mensagem. O
//! ML-DSA roda em modo puro com o contexto FIPS 204 `"diagnos-sa-request-v1"`
//! (separação de domínio: uma assinatura feita aqui nunca pode ser
//! reaproveitada como de outro protocolo que use a mesma chave). As
//! requisições usam a variante hedged — 32 bytes aleatórios novos misturados,
//! que resiste melhor a ataque de falha e de canal lateral, como a referência
//! em TypeScript — e `deterministic` (`rnd` = 32 bytes zero) existe para os
//! vetores normativos fixarem cada byte. O cofre aceita as duas e exige as
//! duas metades.

use ed25519_dalek::{Signer as _, SigningKey, Verifier as _};
use ml_dsa::{EncodedVerifyingKey, ExpandedSigningKey, MlDsa65, Signature, VerifyingKey};
// 🇺🇸 The seal side (`hybrid::Identity`) stores ML-KEM's FIPS 203 expanded encoding — see `hybrid/identity.rs`.
// 🇧🇷 O lado do selo (`hybrid::Identity`) guarda a codificação expandida da FIPS 203 — ver `hybrid/identity.rs`.
#[allow(deprecated)]
use ml_kem::ExpandedKeyEncoding;
use ml_kem::{DecapsulationKey, MlKem768};
use zeroize::Zeroizing;

use crate::error::{expect_len, Error};
use crate::hybrid::Identity;
use crate::kdf;
use crate::locked::LockedBuffer;
use crate::rng::OsRandom;

/// 🇺🇸 HKDF salt of every derivation. 🇧🇷 Salt do HKDF de toda derivação.
pub const SALT: &[u8] = b"diagnos-sa-token-v1";
/// 🇺🇸 FIPS 204 context of every request signature. 🇧🇷 Contexto FIPS 204 de toda assinatura de requisição.
pub const REQUEST_CONTEXT: &[u8] = b"diagnos-sa-request-v1";
/// 🇺🇸 Ed25519 public key. 🇧🇷 Chave pública Ed25519.
pub const ED25519_PUBLIC_BYTES: usize = 32;
/// 🇺🇸 ML-DSA-65 public key (FIPS 204). 🇧🇷 Chave pública ML-DSA-65 (FIPS 204).
pub const MLDSA65_PUBLIC_BYTES: usize = 1952;
/// 🇺🇸 Ed25519 signature. 🇧🇷 Assinatura Ed25519.
pub const ED25519_SIGNATURE_BYTES: usize = 64;
/// 🇺🇸 ML-DSA-65 signature. 🇧🇷 Assinatura ML-DSA-65.
pub const MLDSA65_SIGNATURE_BYTES: usize = 3309;
/// 🇺🇸 The concatenated hybrid signature. 🇧🇷 A assinatura híbrida concatenada.
pub const SIGNATURE_BYTES: usize = ED25519_SIGNATURE_BYTES + MLDSA65_SIGNATURE_BYTES;

/// 🇺🇸 `HKDF-SHA-256(seed, SALT, label)` into `N` zeroizing bytes. 🇧🇷 `HKDF-SHA-256(seed, SALT, rótulo)` em `N` bytes que se zeram.
pub fn derive<const N: usize>(seed: &[u8], label: &str) -> Result<Zeroizing<[u8; N]>, Error> {
    let mut out = Zeroizing::new([0u8; N]);
    kdf::hkdf_sha256(seed, Some(SALT), label.as_bytes(), &mut out[..])?;
    Ok(out)
}

/// 🇺🇸 The ML-DSA-65 signing key of a ξ held in a locked page. 🇧🇷 A chave ML-DSA-65 de um ξ guardado numa página travada.
fn mldsa_key(xi: &[u8]) -> Result<ExpandedSigningKey<MlDsa65>, Error> {
    let xi = ml_dsa::B32::try_from(xi).map_err(|_| Error::InvalidKey)?;
    Ok(ExpandedSigningKey::<MlDsa65>::from_seed(&xi))
}

/// 🇺🇸 The Ed25519 signing key of a 32-byte seed. 🇧🇷 A chave Ed25519 de uma semente de 32 bytes.
fn ed25519_key(seed: &[u8]) -> Result<SigningKey, Error> {
    let mut array = Zeroizing::new([0u8; 32]);
    expect_len("ed25519 seed", seed, 32)?;
    array.copy_from_slice(seed);
    Ok(SigningKey::from_bytes(&array))
}

/// 🇺🇸 Everything a token seed derives, private halves locked. 🇧🇷 Tudo que a semente deriva, metades privadas travadas.
pub struct Keys {
    ed25519_seed: LockedBuffer,
    mldsa_xi: LockedBuffer,
    ed25519_public: [u8; ED25519_PUBLIC_BYTES],
    mldsa65_public: Vec<u8>,
    kem: Identity,
}

impl Keys {
    /// 🇺🇸 Derives the four key pairs from a 32-byte seed. 🇧🇷 Deriva os quatro pares de uma semente de 32 bytes.
    pub fn from_seed(seed: &[u8]) -> Result<Self, Error> {
        expect_len("token seed", seed, super::SEED_BYTES)?;
        let ed25519 = derive::<32>(seed, "ed25519")?;
        let xi = derive::<32>(seed, "ml-dsa-65")?;
        let x25519 = derive::<32>(seed, "x25519")?;
        let d_z = derive::<64>(seed, "ml-kem-768")?;

        let ed25519_public = ed25519_key(&ed25519[..])?.verifying_key().to_bytes();
        let mldsa65_public = mldsa_key(&xi[..])?.verifying_key().encode().to_vec();
        // 🇺🇸 `from_seed(d ‖ z)` is FIPS 203 `KeyGen_internal(d, z)`. 🇧🇷 `from_seed(d ‖ z)` é o `KeyGen_internal(d, z)` da FIPS 203.
        let dk = DecapsulationKey::<MlKem768>::from_seed(ml_kem::Seed::from(*d_z));
        #[allow(deprecated)]
        let expanded = Zeroizing::new(dk.to_expanded_bytes());
        let kem = Identity::from_secrets(&x25519[..], expanded.as_ref())?;
        Ok(Self {
            ed25519_seed: LockedBuffer::from_slice(&ed25519[..])?,
            mldsa_xi: LockedBuffer::from_slice(&xi[..])?,
            ed25519_public,
            mldsa65_public,
            kem,
        })
    }

    /// 🇺🇸 Ed25519 public key. 🇧🇷 Chave pública Ed25519.
    #[must_use]
    pub fn ed25519_public(&self) -> &[u8; ED25519_PUBLIC_BYTES] {
        &self.ed25519_public
    }

    /// 🇺🇸 ML-DSA-65 public key. 🇧🇷 Chave pública ML-DSA-65.
    #[must_use]
    pub fn mldsa65_public(&self) -> &[u8] {
        &self.mldsa65_public
    }

    /// 🇺🇸 The X25519 + ML-KEM-768 pair that opens seals. 🇧🇷 O par X25519 + ML-KEM-768 que abre selos.
    #[must_use]
    pub fn kem(&self) -> &Identity {
        &self.kem
    }

    /// 🇺🇸 `ed25519(message) ‖ ml-dsa-65(message, ctx)`; ML-DSA hedged unless `deterministic` (vectors only).
    /// 🇧🇷 `ed25519(message) ‖ ml-dsa-65(message, ctx)`; ML-DSA hedged, salvo `deterministic` (só vetores).
    pub fn sign(&self, message: &[u8], deterministic: bool) -> Result<Vec<u8>, Error> {
        let classic =
            self.ed25519_seed.with_bytes(|seed| ed25519_key(seed).map(|key| key.sign(message).to_bytes()))??;
        let post_quantum = self.mldsa_xi.with_bytes(|xi| {
            let key = mldsa_key(xi)?;
            let signed = if deterministic {
                key.sign_deterministic(message, REQUEST_CONTEXT)
            } else {
                key.sign_randomized(message, REQUEST_CONTEXT, &mut OsRandom)
            };
            signed.map_err(|_| Error::Random)
        })??;
        let mut signature = Vec::with_capacity(SIGNATURE_BYTES);
        signature.extend_from_slice(&classic);
        signature.extend_from_slice(&post_quantum.encode());
        Ok(signature)
    }

    /// 🇺🇸 Zeroes every private half now. 🇧🇷 Zera toda metade privada agora.
    pub fn wipe(&mut self) {
        self.ed25519_seed.wipe();
        self.mldsa_xi.wipe();
        self.kem.wipe();
    }

    /// 🇺🇸 Whether `wipe()` already ran. 🇧🇷 Se `wipe()` já rodou.
    #[must_use]
    pub fn is_wiped(&self) -> bool {
        self.ed25519_seed.is_wiped()
    }
}

/// 🇺🇸 What the vault checks: exact length, and BOTH halves valid. 🇧🇷 O que o cofre confere: tamanho exato e AS DUAS metades.
#[must_use]
pub fn verify(ed25519_public: &[u8], mldsa65_public: &[u8], message: &[u8], signature: &[u8]) -> bool {
    if signature.len() != SIGNATURE_BYTES {
        return false;
    }
    let (classic, post_quantum) = signature.split_at(ED25519_SIGNATURE_BYTES);
    let classic_ok = <[u8; ED25519_PUBLIC_BYTES]>::try_from(ed25519_public)
        .ok()
        .and_then(|bytes| ed25519_dalek::VerifyingKey::from_bytes(&bytes).ok())
        .zip(ed25519_dalek::Signature::from_slice(classic).ok())
        .is_some_and(|(key, sig)| key.verify(message, &sig).is_ok());
    let post_quantum_ok = EncodedVerifyingKey::<MlDsa65>::try_from(mldsa65_public)
        .ok()
        .map(|encoded| VerifyingKey::<MlDsa65>::decode(&encoded))
        .zip(Signature::<MlDsa65>::try_from(post_quantum).ok())
        .is_some_and(|(key, sig)| key.verify_with_context(message, REQUEST_CONTEXT, &sig));
    classic_ok && post_quantum_ok
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hybrid::seal;

    #[test]
    fn derives_keys_of_the_documented_sizes_deterministically() {
        let keys = Keys::from_seed(&[7u8; 32]).unwrap();
        let again = Keys::from_seed(&[7u8; 32]).unwrap();
        assert_eq!(keys.ed25519_public(), again.ed25519_public());
        assert_eq!(keys.mldsa65_public().len(), MLDSA65_PUBLIC_BYTES);
        assert_eq!(keys.mldsa65_public(), again.mldsa65_public());
        assert_eq!(keys.kem().x25519_public(), again.kem().x25519_public());
        assert_eq!(keys.kem().mlkem768_public(), again.kem().mlkem768_public());
        let other = Keys::from_seed(&[8u8; 32]).unwrap();
        assert_ne!(keys.ed25519_public(), other.ed25519_public());
        assert!(Keys::from_seed(&[7u8; 31]).is_err());
    }

    #[test]
    fn signs_with_both_halves_and_verifies_only_both() {
        let keys = Keys::from_seed(&[7u8; 32]).unwrap();
        let signature = keys.sign(b"base", true).unwrap();
        assert_eq!(signature.len(), SIGNATURE_BYTES);
        assert_eq!(signature, keys.sign(b"base", true).unwrap());
        // 🇺🇸 Hedged: same Ed25519 half, a fresh ML-DSA half, both valid. 🇧🇷 Hedged: mesma metade Ed25519, ML-DSA nova, ambas válidas.
        let hedged = keys.sign(b"base", false).unwrap();
        assert_eq!(hedged[..64], signature[..64]);
        assert_ne!(hedged, keys.sign(b"base", false).unwrap());
        assert!(verify(keys.ed25519_public(), keys.mldsa65_public(), b"base", &hedged));
        assert!(verify(keys.ed25519_public(), keys.mldsa65_public(), b"base", &signature));
        assert!(!verify(keys.ed25519_public(), keys.mldsa65_public(), b"other", &signature));
        for index in [0, ED25519_SIGNATURE_BYTES + 10] {
            let mut broken = signature.clone();
            broken[index] ^= 1;
            assert!(!verify(keys.ed25519_public(), keys.mldsa65_public(), b"base", &broken));
        }
        assert!(!verify(keys.ed25519_public(), keys.mldsa65_public(), b"base", &signature[..64]));
    }

    #[test]
    fn opens_what_is_sealed_to_its_kem_pair_and_wipes() {
        let mut keys = Keys::from_seed(&[9u8; 32]).unwrap();
        let sealed = seal(keys.kem().x25519_public(), keys.kem().mlkem768_public(), b"kek", b"aad").unwrap();
        let opened = keys.kem().open(&sealed.encapsulation, &sealed.nonce, &sealed.ciphertext, b"aad").unwrap();
        assert_eq!(&*opened, b"kek");
        keys.wipe();
        assert!(keys.is_wiped());
        assert!(keys.sign(b"base", false).is_err());
    }
}
