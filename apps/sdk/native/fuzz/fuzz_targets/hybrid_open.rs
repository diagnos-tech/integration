//! 🇺🇸 `Identity::open` against any encapsulation, nonce and ciphertext: a forged seal fails cleanly, never
//! panics, and a real seal of the same bytes opens to exactly them.
//!
//! 🇧🇷 `Identity::open` contra qualquer encapsulamento, nonce e ciphertext: um selo forjado falha limpo, nunca
//! entra em pânico, e um selo de verdade dos mesmos bytes abre exatamente para eles.

#![no_main]

use _secure::aead::NONCE_BYTES;
use _secure::hybrid::{self, Identity, ENCAPSULATION_BYTES};
use libfuzzer_sys::fuzz_target;

thread_local! {
    // 🇺🇸 One recipient for the whole run: generating ML-KEM keys per input would drown the fuzzer.
    // 🇧🇷 Um destinatário para a execução inteira: gerar chaves ML-KEM por entrada afogaria o fuzzer.
    static RECIPIENT: Identity = Identity::generate().expect("the enclave holds one identity");
}

fuzz_target!(|data: &[u8]| {
    RECIPIENT.with(|recipient| {
        // 🇺🇸 The input as a hostile seal: rejected or opened, never a crash.
        // 🇧🇷 A entrada como selo hostil: rejeitado ou aberto, nunca um crash.
        if let Some((encapsulation, rest)) = data.split_at_checked(ENCAPSULATION_BYTES) {
            if let Some((nonce, ciphertext)) = rest.split_at_checked(NONCE_BYTES) {
                let _ = recipient.open(encapsulation, nonce, ciphertext, &[]);
            }
        }

        // 🇺🇸 The input as a message: sealed to the recipient, it opens to exactly itself.
        // 🇧🇷 A entrada como mensagem: selada para o destinatário, abre exatamente para si mesma.
        let sealed = hybrid::seal(recipient.x25519_public(), recipient.mlkem768_public(), data, &[])
            .expect("a well-formed recipient can always be sealed to");
        let opened =
            recipient.open(&sealed.encapsulation, &sealed.nonce, &sealed.ciphertext, &[]).expect("a real seal opens");
        assert_eq!(opened.as_slice(), data);
    });
});
