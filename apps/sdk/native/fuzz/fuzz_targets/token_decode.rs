//! 🇺🇸 `token::decode` against any text: a hostile or mangled token is refused with a code, never a panic, and a
//! token built from the same bytes decodes back to exactly them and signs verifiably.
//!
//! 🇧🇷 `token::decode` contra qualquer texto: um token hostil ou mutilado é recusado com um código, nunca um pânico,
//! e um token montado dos mesmos bytes decodifica de volta exatamente para eles e assina de forma verificável.

#![no_main]

use _secure::token::{self, Keys, KEY_ID_BYTES, PREFIX, SEED_BYTES};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // 🇺🇸 The input as pasted text, with and without the prefix: decoded or refused, never a crash.
    // 🇧🇷 A entrada como texto colado, com e sem o prefixo: decodificado ou recusado, nunca um crash.
    if let Ok(text) = std::str::from_utf8(data) {
        let _ = token::decode(text);
        let _ = token::decode(&format!("{PREFIX}{text}"));
    }

    // 🇺🇸 The input as token parts: a valid workspace round-trips, and the derived keys sign verifiably.
    // 🇧🇷 A entrada como partes de token: um workspace válido faz a ida e volta, e as chaves derivadas assinam.
    if let Some((parts, workspace)) = data.split_at_checked(KEY_ID_BYTES + SEED_BYTES) {
        let (key_id, seed) = parts.split_at(KEY_ID_BYTES);
        let Ok(workspace) = std::str::from_utf8(workspace) else { return };
        let Ok(text) = token::encode(key_id, seed, workspace) else { return };
        let decoded = token::decode(&text).expect("an encoded token decodes");
        assert_eq!(decoded.key_id.as_slice(), key_id);
        assert_eq!(decoded.seed.as_slice(), seed);
        assert_eq!(decoded.workspace_id, workspace);
        let keys = Keys::from_seed(seed).expect("any 32 bytes are a seed");
        let signature = keys.sign(data, false).expect("the enclave signs");
        assert!(token::verify(keys.ed25519_public(), keys.mldsa65_public(), data, &signature));
    }
});
