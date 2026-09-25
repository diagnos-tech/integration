//! 🇺🇸 AES-256-GCM, the one AEAD of the protocol (`docs/PROTOCOL.md §4, §6, §7`).
//!
//! Nonces are never generated here: the caller draws them from the entropy
//! pool (or, for the vault's own envelopes, receives them on the wire), so
//! this module has no randomness and no state — it is a pure function of
//! (key, nonce, data, aad), which is what makes it trivially testable against
//! the TypeScript vectors.
//!
//! 🇧🇷 AES-256-GCM, o único AEAD do protocolo (`docs/PROTOCOL.md §4, §6, §7`).
//!
//! Nonces nunca são gerados aqui: quem chama os tira do pool de entropia (ou,
//! para os envelopes do próprio cofre, os recebe pelo fio), então este módulo
//! não tem aleatoriedade nem estado — é uma função pura de (chave, nonce,
//! dados, aad), o que o torna trivialmente testável contra os vetores em
//! TypeScript.

use aes_gcm::aead::{Aead, Nonce, Payload};
use aes_gcm::{Aes256Gcm, Key, KeyInit};
use zeroize::Zeroizing;

use crate::error::{expect_len, Error};

/// 🇺🇸 AES-256 key length. 🇧🇷 Tamanho da chave AES-256.
pub const KEY_BYTES: usize = 32;
/// 🇺🇸 GCM nonce length the protocol fixes (96 bits). 🇧🇷 Tamanho de nonce GCM que o protocolo fixa (96 bits).
pub const NONCE_BYTES: usize = 12;
/// 🇺🇸 GCM tag length, appended to the ciphertext. 🇧🇷 Tamanho da tag GCM, anexada ao ciphertext.
pub const TAG_BYTES: usize = 16;

fn cipher(key: &[u8]) -> Result<Aes256Gcm, Error> {
    expect_len("aes-gcm key", key, KEY_BYTES)?;
    let key: &Key<Aes256Gcm> = key.try_into().map_err(|_| Error::InvalidKey)?;
    Ok(Aes256Gcm::new(key))
}

fn nonce(nonce: &[u8]) -> Result<&Nonce<Aes256Gcm>, Error> {
    expect_len("aes-gcm nonce", nonce, NONCE_BYTES)?;
    nonce.try_into().map_err(|_| Error::InvalidLength {
        what: "aes-gcm nonce",
        expected: NONCE_BYTES,
        got: nonce.len(),
    })
}

/// 🇺🇸 `ciphertext ‖ tag` for `plaintext` under `key`/`nonce`, authenticating `aad`.
/// 🇧🇷 `ciphertext ‖ tag` de `plaintext` sob `key`/`nonce`, autenticando `aad`.
pub fn seal(key: &[u8], nonce_bytes: &[u8], plaintext: &[u8], aad: &[u8]) -> Result<Vec<u8>, Error> {
    let cipher = cipher(key)?;
    let nonce = nonce(nonce_bytes)?;
    cipher.encrypt(nonce, Payload { msg: plaintext, aad }).map_err(|_| Error::DidNotOpen)
}

/// 🇺🇸 The inverse of [`seal`]; every failure is [`Error::DidNotOpen`], by design.
/// 🇧🇷 O inverso de [`seal`]; toda falha é [`Error::DidNotOpen`], de propósito.
pub fn open(key: &[u8], nonce_bytes: &[u8], ciphertext: &[u8], aad: &[u8]) -> Result<Zeroizing<Vec<u8>>, Error> {
    let cipher = cipher(key)?;
    let nonce = nonce(nonce_bytes)?;
    if ciphertext.len() < TAG_BYTES {
        return Err(Error::DidNotOpen);
    }
    cipher.decrypt(nonce, Payload { msg: ciphertext, aad }).map(Zeroizing::new).map_err(|_| Error::DidNotOpen)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_with_aad() {
        let key = [7u8; 32];
        let nonce = [9u8; 12];
        let sealed = seal(&key, &nonce, b"clinical", b"ctx").unwrap();
        assert_eq!(sealed.len(), 8 + TAG_BYTES);
        assert_eq!(&*open(&key, &nonce, &sealed, b"ctx").unwrap(), b"clinical");
        assert_eq!(open(&key, &nonce, &sealed, b"other").unwrap_err(), Error::DidNotOpen);
    }

    #[test]
    fn rejects_wrong_lengths() {
        assert!(matches!(seal(&[0u8; 31], &[0u8; 12], b"", b""), Err(Error::InvalidLength { .. })));
        assert!(matches!(seal(&[0u8; 32], &[0u8; 11], b"", b""), Err(Error::InvalidLength { .. })));
        assert_eq!(open(&[0u8; 32], &[0u8; 12], &[0u8; 15], b"").unwrap_err(), Error::DidNotOpen);
    }
}
