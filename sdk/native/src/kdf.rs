//! 🇺🇸 The two derivation primitives of the protocol: HMAC-SHA512 (request signatures) and HKDF-SHA256 (every key).
//!
//! Both operate on borrowed slices and return fixed-size stack values, so a
//! caller holding a locked page can derive without the key ever being copied
//! to the heap. `docs/PROTOCOL.md §3` (signature) and §6/§7/§9 (HKDF uses).
//!
//! 🇧🇷 As duas primitivas de derivação do protocolo: HMAC-SHA512 (assinatura de requisição) e HKDF-SHA256 (toda chave).
//!
//! As duas operam sobre slices emprestadas e devolvem valores de tamanho fixo
//! na pilha, então quem segura uma página travada deriva sem a chave nunca
//! ser copiada para o heap. `docs/PROTOCOL.md §3` (assinatura) e §6/§7/§9
//! (usos de HKDF).

use hkdf::Hkdf;
use hmac::{Hmac, KeyInit, Mac};
use sha2::{Sha256, Sha512};

use crate::error::Error;

/// 🇺🇸 Bytes of an HMAC-SHA512 tag. 🇧🇷 Bytes de uma tag HMAC-SHA512.
pub const HMAC_SHA512_BYTES: usize = 64;

/// 🇺🇸 RFC 5869 caps HKDF output at `255 × HashLen`. 🇧🇷 A RFC 5869 limita a saída do HKDF a `255 × HashLen`.
pub const HKDF_SHA256_MAX_BYTES: usize = 255 * 32;

/// 🇺🇸 HMAC-SHA512 over `message`; any key length is valid per RFC 2104.
/// 🇧🇷 HMAC-SHA512 sobre `message`; qualquer tamanho de chave é válido pela RFC 2104.
pub fn hmac_sha512(key: &[u8], message: &[u8]) -> Result<[u8; HMAC_SHA512_BYTES], Error> {
    let mut mac = Hmac::<Sha512>::new_from_slice(key).map_err(|_| Error::InvalidKey)?;
    mac.update(message);
    let tag = mac.finalize().into_bytes();
    let mut out = [0u8; HMAC_SHA512_BYTES];
    out.copy_from_slice(&tag);
    Ok(out)
}

/// 🇺🇸 HKDF-SHA256 into `okm`; `salt = None` is the RFC's zero-filled salt, exactly what the TypeScript reference does.
/// 🇧🇷 HKDF-SHA256 em `okm`; `salt = None` é o salt de zeros da RFC, exatamente o que a referência em TypeScript faz.
pub fn hkdf_sha256(ikm: &[u8], salt: Option<&[u8]>, info: &[u8], okm: &mut [u8]) -> Result<(), Error> {
    if okm.is_empty() || okm.len() > HKDF_SHA256_MAX_BYTES {
        return Err(Error::InvalidLength {
            what: "hkdf output length",
            expected: HKDF_SHA256_MAX_BYTES,
            got: okm.len(),
        });
    }
    Hkdf::<Sha256>::new(salt, ikm).expand(info, okm).map_err(|_| Error::InvalidLength {
        what: "hkdf output length",
        expected: HKDF_SHA256_MAX_BYTES,
        got: okm.len(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hmac_sha512_matches_rfc4231_case_2() {
        let tag = hmac_sha512(b"Jefe", b"what do ya want for nothing?").unwrap();
        let expected = "164b7a7bfcf819e2e395fbe73b56e0a387bd64222e831fd610270cd7ea2505549758bf75c05a994a6d034f65f8f0e6fdcaeab1a34d4a6b4b636e070a38bce737";
        assert_eq!(hex(&tag), expected);
    }

    #[test]
    fn hkdf_sha256_matches_rfc5869_case_1() {
        let ikm = [0x0bu8; 22];
        let salt: Vec<u8> = (0x00u8..=0x0c).collect();
        let info: Vec<u8> = (0xf0u8..=0xf9).collect();
        let mut okm = [0u8; 42];
        hkdf_sha256(&ikm, Some(&salt), &info, &mut okm).unwrap();
        let expected = "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865";
        assert_eq!(hex(&okm), expected);
    }

    #[test]
    fn hkdf_rejects_empty_and_oversized_output() {
        let mut empty: [u8; 0] = [];
        assert!(hkdf_sha256(b"k", None, b"i", &mut empty).is_err());
        let mut huge = vec![0u8; HKDF_SHA256_MAX_BYTES + 1];
        assert!(hkdf_sha256(b"k", None, b"i", &mut huge).is_err());
    }

    fn hex(data: &[u8]) -> String {
        use std::fmt::Write as _;
        data.iter().fold(String::new(), |mut out, b| {
            let _ = write!(out, "{b:02x}");
            out
        })
    }
}
