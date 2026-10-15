//! 🇺🇸 Ed25519 with the seed held in a [`SecretBox`]: the service account credential's signature (`docs/PROTOCOL.md §1`).
//!
//! The credential's private half is a 32-byte RFC 8032 seed. It enters the
//! enclave once, when the SDK parses `DIAGNOS_CREDENTIAL` or the credential
//! file, and from then on only two things ever leave: the public key, which
//! is not secret, and a signature over a message the caller chose. The
//! expanded signing key lives on the stack for the duration of one call and
//! is zeroed on drop (`ed25519-dalek`'s `zeroize` feature), so the secret
//! never exists in the Python heap at all. Signing is deterministic
//! (RFC 8032 §5.1.6): no randomness to get wrong, and the same message under
//! the same seed always yields the same signature — which is what makes the
//! RFC 8032 vector below a full check of the implementation.
//!
//! 🇧🇷 Ed25519 com a semente guardada num [`SecretBox`]: a assinatura da credencial de conta de serviço (`docs/PROTOCOL.md §1`).
//!
//! A metade privada da credencial é uma semente RFC 8032 de 32 bytes. Ela
//! entra no enclave uma vez, quando o SDK lê `DIAGNOS_CREDENTIAL` ou o arquivo
//! de credencial, e daí em diante só duas coisas saem: a chave pública, que não
//! é segredo, e uma assinatura sobre uma mensagem que quem chama escolheu. A
//! chave de assinatura expandida vive na pilha durante uma chamada e é zerada
//! no drop (feature `zeroize` do `ed25519-dalek`), então o segredo nunca
//! existe no heap do Python. A assinatura é determinística (RFC 8032 §5.1.6):
//! nenhuma aleatoriedade para errar, e a mesma mensagem sob a mesma semente
//! sempre dá a mesma assinatura — o que faz do vetor da RFC 8032 abaixo uma
//! conferência completa da implementação.

use ed25519_dalek::{Signer, SigningKey, PUBLIC_KEY_LENGTH, SECRET_KEY_LENGTH, SIGNATURE_LENGTH};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use zeroize::Zeroizing;

use crate::buffer::read_bytes;
use crate::error::Error;
use crate::secret_box::SecretBox;

/// 🇺🇸 Bytes of an Ed25519 seed (the private key). 🇧🇷 Bytes de uma semente Ed25519 (a chave privada).
pub const ED25519_SEED_BYTES: usize = SECRET_KEY_LENGTH;
/// 🇺🇸 Bytes of an Ed25519 public key. 🇧🇷 Bytes de uma chave pública Ed25519.
pub const ED25519_PUBLIC_BYTES: usize = PUBLIC_KEY_LENGTH;
/// 🇺🇸 Bytes of an Ed25519 signature. 🇧🇷 Bytes de uma assinatura Ed25519.
pub const ED25519_SIGNATURE_BYTES: usize = SIGNATURE_LENGTH;

/// 🇺🇸 The signing key for `seed`, refusing any length but 32 bytes.
/// 🇧🇷 A chave de assinatura de `seed`, recusando qualquer tamanho fora 32 bytes.
fn signing_key(seed: &[u8]) -> Result<SigningKey, Error> {
    let array: Zeroizing<[u8; ED25519_SEED_BYTES]> =
        Zeroizing::new(seed.try_into().map_err(|_| Error::InvalidLength {
            what: "ed25519 seed",
            expected: ED25519_SEED_BYTES,
            got: seed.len(),
        })?);
    Ok(SigningKey::from_bytes(&array))
}

/// 🇺🇸 The RFC 8032 public key of `seed`. 🇧🇷 A chave pública RFC 8032 de `seed`.
pub fn public_key(seed: &[u8]) -> Result<[u8; ED25519_PUBLIC_BYTES], Error> {
    Ok(signing_key(seed)?.verifying_key().to_bytes())
}

/// 🇺🇸 The RFC 8032 (pure Ed25519) signature of `message` under `seed`.
/// 🇧🇷 A assinatura RFC 8032 (Ed25519 puro) de `message` sob `seed`.
pub fn sign(seed: &[u8], message: &[u8]) -> Result<[u8; ED25519_SIGNATURE_BYTES], Error> {
    Ok(signing_key(seed)?.sign(message).to_bytes())
}

/// 🇺🇸 Python: the 32-byte public key of the seed in `seed`. 🇧🇷 Python: a chave pública de 32 bytes da semente em `seed`.
#[pyfunction]
pub fn ed25519_public_key<'py>(py: Python<'py>, seed: PyRef<'py, SecretBox>) -> PyResult<Bound<'py, PyBytes>> {
    let public = seed.with_bytes(public_key)??;
    Ok(PyBytes::new(py, &public))
}

/// 🇺🇸 Python: the 64-byte signature of `message` under the seed in `seed`.
/// 🇧🇷 Python: a assinatura de 64 bytes de `message` sob a semente em `seed`.
#[pyfunction]
pub fn ed25519_sign<'py>(
    py: Python<'py>,
    seed: PyRef<'py, SecretBox>,
    message: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyBytes>> {
    let message = read_bytes(message)?;
    let signature = seed.with_bytes(|key| sign(key, &message))??;
    Ok(PyBytes::new(py, &signature))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unhex(text: &str) -> Vec<u8> {
        (0..text.len()).step_by(2).map(|i| u8::from_str_radix(&text[i..i + 2], 16).unwrap()).collect()
    }

    /// 🇺🇸 RFC 8032 §7.1, TEST 1 (empty message) and TEST 2 (one byte).
    /// 🇧🇷 RFC 8032 §7.1, TEST 1 (mensagem vazia) e TEST 2 (um byte).
    #[test]
    fn matches_rfc8032_vectors() {
        let cases = [
            (
                "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
                "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
                "",
                "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
            ),
            (
                "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
                "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
                "72",
                "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
            ),
        ];
        for (seed, public, message, signature) in cases {
            let seed = unhex(seed);
            assert_eq!(public_key(&seed).unwrap().to_vec(), unhex(public));
            assert_eq!(sign(&seed, &unhex(message)).unwrap().to_vec(), unhex(signature));
        }
    }

    #[test]
    fn rejects_a_seed_that_is_not_32_bytes() {
        assert!(matches!(public_key(&[7u8; 31]), Err(Error::InvalidLength { got: 31, .. })));
        assert!(matches!(sign(&[7u8; 64], b"m"), Err(Error::InvalidLength { got: 64, .. })));
    }
}
