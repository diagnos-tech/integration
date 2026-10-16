//! 🇺🇸 The token's text form (spec §2): `dgn_sk1_<base64url(key_id ‖ seed ‖ workspace_id ‖ crc32)>`.
//!
//! Decoding runs here, not in Python, because the 32-byte seed sits in the
//! middle of the payload: the bytes go from the pasted text straight into
//! zeroizing memory and then into a locked page, and no Python `bytes` ever
//! holds them. The CRC-32 is not integrity — the signature is — it exists so
//! a token cut short by a terminal, or pasted with a character missing, is
//! named as exactly that before any request leaves the machine. Every
//! failure is a [`TokenError`] code with no byte of the input in it.
//!
//! 🇧🇷 A forma textual do token (spec §2): `dgn_sk1_<base64url(key_id ‖ seed ‖ workspace_id ‖ crc32)>`.
//!
//! A decodificação roda aqui, não no Python, porque a semente de 32 bytes
//! fica no meio do payload: os bytes vão do texto colado direto para memória
//! que se zera e depois para uma página travada, e nenhum `bytes` do Python
//! os guarda. O CRC-32 não é integridade — a assinatura é — e existe para um
//! token cortado pelo terminal, ou colado com um caractere a menos, ser
//! nomeado exatamente assim antes de qualquer requisição sair da máquina. Toda
//! falha é um código [`TokenError`] sem nenhum byte da entrada.

use base64::Engine as _;
use zeroize::Zeroizing;

/// 🇺🇸 Fixed prefix: what secret scanners and the CLI recognize. 🇧🇷 Prefixo fixo: o que scanners e a CLI reconhecem.
pub const PREFIX: &str = "dgn_sk1_";
/// 🇺🇸 Random key id, shown as `svc_<32 hex>`. 🇧🇷 Id aleatório da chave, mostrado como `svc_<32 hex>`.
pub const KEY_ID_BYTES: usize = 16;
/// 🇺🇸 The one secret; everything else derives from it. 🇧🇷 O único segredo; todo o resto deriva dele.
pub const SEED_BYTES: usize = 32;
/// 🇺🇸 CRC-32 (IEEE), big-endian. 🇧🇷 CRC-32 (IEEE), big-endian.
pub const CRC_BYTES: usize = 4;
/// 🇺🇸 A Firestore nanoid; never `:`, `@` or `.`, so `svc_…@<ws>.diagnos.health` is unambiguous. 🇧🇷 Um nanoid do Firestore; nunca `:`, `@` nem `.`.
pub const MAX_WORKSPACE_BYTES: usize = 64;

/// 🇺🇸 Why a text is not a token — a code, never the text. 🇧🇷 Por que um texto não é token — um código, nunca o texto.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TokenError {
    /// 🇺🇸 Does not start with `dgn_sk1_`. 🇧🇷 Não começa com `dgn_sk1_`.
    Prefix,
    /// 🇺🇸 Not canonical base64url without padding. 🇧🇷 Não é base64url canônico sem padding.
    Encoding,
    /// 🇺🇸 Too short to hold key id, seed, a workspace and the CRC. 🇧🇷 Curto demais para id, semente, workspace e CRC.
    Length,
    /// 🇺🇸 The CRC does not match: truncated or pasted wrong. 🇧🇷 O CRC não confere: truncado ou colado errado.
    Checksum,
    /// 🇺🇸 The workspace id is not a nanoid. 🇧🇷 O id do workspace não é um nanoid.
    Workspace,
}

impl TokenError {
    /// 🇺🇸 The stable code Python maps to a message. 🇧🇷 O código estável que o Python mapeia numa mensagem.
    #[must_use]
    pub fn code(self) -> &'static str {
        match self {
            Self::Prefix => "prefix",
            Self::Encoding => "encoding",
            Self::Length => "length",
            Self::Checksum => "checksum",
            Self::Workspace => "workspace",
        }
    }
}

/// 🇺🇸 A decoded token; the seed zeroizes on drop. 🇧🇷 Um token decodificado; a semente se zera ao descartar.
pub struct Decoded {
    /// 🇺🇸 The 16-byte key id. 🇧🇷 O id de 16 bytes da chave.
    pub key_id: [u8; KEY_ID_BYTES],
    /// 🇺🇸 The 32-byte seed. 🇧🇷 A semente de 32 bytes.
    pub seed: Zeroizing<[u8; SEED_BYTES]>,
    /// 🇺🇸 The workspace id (ASCII). 🇧🇷 O id do workspace (ASCII).
    pub workspace_id: String,
}

/// 🇺🇸 CRC-32 (IEEE 802.3, reflected, init and xor-out `0xFFFFFFFF`) over the parts, in order.
/// 🇧🇷 CRC-32 (IEEE 802.3, refletido, init e xor final `0xFFFFFFFF`) sobre as partes, em ordem.
#[must_use]
pub fn crc32(parts: &[&[u8]]) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for byte in parts.iter().flat_map(|part| part.iter()) {
        crc ^= u32::from(*byte);
        for _ in 0..8 {
            crc = if crc & 1 == 1 { (crc >> 1) ^ 0xEDB8_8320 } else { crc >> 1 };
        }
    }
    !crc
}

/// 🇺🇸 The nanoid alphabet, `[A-Za-z0-9_-]`, 1 to 64 bytes. 🇧🇷 O alfabeto do nanoid, `[A-Za-z0-9_-]`, de 1 a 64 bytes.
fn valid_workspace(workspace: &[u8]) -> bool {
    (1..=MAX_WORKSPACE_BYTES).contains(&workspace.len())
        && workspace.iter().all(|b| b.is_ascii_alphanumeric() || *b == b'_' || *b == b'-')
}

/// 🇺🇸 Text → parts. Whitespace at the ends (a terminal paste brings `\n`) is tolerated; the CRC is checked before
/// the workspace id, so a cut token says "truncated".
/// 🇧🇷 Texto → partes. Espaço nas pontas (colar do terminal traz `\n`) é tolerado; o CRC é conferido antes do id do
/// workspace, para um token cortado dizer "truncado".
pub fn decode(text: &str) -> Result<Decoded, TokenError> {
    let body = text.trim().strip_prefix(PREFIX).ok_or(TokenError::Prefix)?;
    let raw = Zeroizing::new(
        base64::engine::general_purpose::URL_SAFE_NO_PAD.decode(body).map_err(|_| TokenError::Encoding)?,
    );
    if raw.len() < KEY_ID_BYTES + SEED_BYTES + 1 + CRC_BYTES {
        return Err(TokenError::Length);
    }
    let (payload, crc) = raw.split_at(raw.len() - CRC_BYTES);
    let mut expected = [0u8; CRC_BYTES];
    expected.copy_from_slice(crc);
    if crc32(&[PREFIX.as_bytes(), payload]) != u32::from_be_bytes(expected) {
        return Err(TokenError::Checksum);
    }
    let workspace = &payload[KEY_ID_BYTES + SEED_BYTES..];
    if !valid_workspace(workspace) {
        return Err(TokenError::Workspace);
    }
    let mut key_id = [0u8; KEY_ID_BYTES];
    key_id.copy_from_slice(&payload[..KEY_ID_BYTES]);
    let mut seed = Zeroizing::new([0u8; SEED_BYTES]);
    seed.copy_from_slice(&payload[KEY_ID_BYTES..KEY_ID_BYTES + SEED_BYTES]);
    let workspace_id = String::from_utf8(workspace.to_vec()).map_err(|_| TokenError::Workspace)?;
    Ok(Decoded { key_id, seed, workspace_id })
}

/// 🇺🇸 Parts → text: what the browser does once, at creation; here for tests and tooling only.
/// 🇧🇷 Partes → texto: o que o navegador faz uma vez, na criação; aqui só para testes e ferramentas.
pub fn encode(key_id: &[u8], seed: &[u8], workspace_id: &str) -> Result<Zeroizing<String>, TokenError> {
    if key_id.len() != KEY_ID_BYTES || seed.len() != SEED_BYTES {
        return Err(TokenError::Length);
    }
    if !valid_workspace(workspace_id.as_bytes()) {
        return Err(TokenError::Workspace);
    }
    let mut raw = Zeroizing::new(Vec::with_capacity(KEY_ID_BYTES + SEED_BYTES + workspace_id.len() + CRC_BYTES));
    raw.extend_from_slice(key_id);
    raw.extend_from_slice(seed);
    raw.extend_from_slice(workspace_id.as_bytes());
    let crc = crc32(&[PREFIX.as_bytes(), &raw]);
    raw.extend_from_slice(&crc.to_be_bytes());
    let mut text = Zeroizing::new(String::from(PREFIX));
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode_string(&raw[..], &mut text);
    Ok(text)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Zeroizing<String> {
        encode(&[0x11; KEY_ID_BYTES], &[0x22; SEED_BYTES], "ws_Test-1").unwrap()
    }

    #[test]
    fn crc32_matches_the_ieee_check_value() {
        // 🇺🇸 The catalogue check value of CRC-32/ISO-HDLC. 🇧🇷 O valor de conferência do catálogo para CRC-32/ISO-HDLC.
        assert_eq!(crc32(&[b"123456789"]), 0xCBF4_3926);
        assert_eq!(crc32(&[b"1234", b"56789"]), 0xCBF4_3926);
    }

    #[test]
    fn round_trips_and_has_the_documented_size() {
        let text = sample();
        assert!(text.starts_with(PREFIX));
        // 🇺🇸 ~100 characters, as the spec says. 🇧🇷 ~100 caracteres, como a spec diz.
        assert_eq!(text.len(), PREFIX.len() + ((KEY_ID_BYTES + SEED_BYTES + 9 + CRC_BYTES) * 4).div_ceil(3));
        let decoded = decode(&text).unwrap();
        assert_eq!(decoded.key_id, [0x11; KEY_ID_BYTES]);
        assert_eq!(*decoded.seed, [0x22; SEED_BYTES]);
        assert_eq!(decoded.workspace_id, "ws_Test-1");
    }

    #[test]
    fn names_each_failure() {
        let text = sample();
        assert_eq!(decode("apikey-x").err(), Some(TokenError::Prefix));
        assert_eq!(decode(&format!("{}=", &text[..])).err(), Some(TokenError::Encoding));
        assert_eq!(decode(&format!("{PREFIX}/{}", &text[PREFIX.len() + 1..])).err(), Some(TokenError::Encoding));
        assert_eq!(decode(&format!("{PREFIX}AAAA")).err(), Some(TokenError::Length));
        // 🇺🇸 Cut short: either the tail is no longer canonical base64url or the CRC no longer matches — Python
        //    says "truncated or pasted wrong" for both. Then one character changed, which only the CRC can see.
        // 🇧🇷 Cortado: ou o fim deixa de ser base64url canônico ou o CRC deixa de conferir — o Python diz
        //    "truncado ou colado errado" para os dois. Depois um caractere trocado, que só o CRC enxerga.
        for cut in 1..=8 {
            let error = decode(&text[..text.len() - cut]).err();
            assert!(matches!(error, Some(TokenError::Encoding | TokenError::Checksum)), "cut {cut}: {error:?}");
        }
        let mut swapped = text.to_string();
        let middle = PREFIX.len() + 30;
        let replacement = if &swapped[middle..=middle] == "A" { "B" } else { "A" };
        swapped.replace_range(middle..=middle, replacement);
        assert_eq!(decode(&swapped).err(), Some(TokenError::Checksum));
        assert_eq!(encode(&[0; KEY_ID_BYTES], &[0; SEED_BYTES], "no spaces").err(), Some(TokenError::Workspace));
        assert_eq!(encode(&[0; 15], &[0; SEED_BYTES], "ws").err(), Some(TokenError::Length));
        assert_eq!(TokenError::Checksum.code(), "checksum");
    }
}
