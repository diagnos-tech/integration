//! 🇺🇸 `aead::open` against any key, nonce, AAD and ciphertext: a forgery fails cleanly, never panics, and
//! whatever was sealed opens to exactly itself.
//!
//! 🇧🇷 `aead::open` contra qualquer chave, nonce, AAD e ciphertext: uma falsificação falha limpa, nunca entra
//! em pânico, e o que foi selado abre exatamente para si mesmo.

#![no_main]

use _secure::aead;
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Some((key, rest)) = data.split_at_checked(aead::KEY_BYTES) else { return };
    let Some((nonce, rest)) = rest.split_at_checked(aead::NONCE_BYTES) else { return };
    let Some((&aad_len, rest)) = rest.split_first() else { return };
    let (aad, payload) = rest.split_at(usize::from(aad_len).min(rest.len()));

    // 🇺🇸 The payload as a hostile ciphertext: rejected or opened, never a crash.
    // 🇧🇷 O payload como ciphertext hostil: rejeitado ou aberto, nunca um crash.
    let _ = aead::open(key, nonce, payload, aad);

    // 🇺🇸 The same payload as a message: sealing and opening must round-trip.
    // 🇧🇷 O mesmo payload como mensagem: selar e abrir precisam voltar ao início.
    let sealed = aead::seal(key, nonce, payload, aad).expect("a well-sized key and nonce always seal");
    let opened = aead::open(key, nonce, &sealed, aad).expect("what was sealed opens");
    assert_eq!(opened.as_slice(), payload);
});
