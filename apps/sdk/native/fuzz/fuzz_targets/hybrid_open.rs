//! `Identity::open` against any encapsulation, nonce and ciphertext: a forged seal fails cleanly, never
//! panics, and a real seal of the same bytes opens to exactly them.

#![no_main]

use _secure::aead::NONCE_BYTES;
use _secure::hybrid::{self, Identity, ENCAPSULATION_BYTES};
use libfuzzer_sys::fuzz_target;

thread_local! {
    // One recipient for the whole run: generating ML-KEM keys per input would drown the fuzzer.
    static RECIPIENT: Identity = Identity::generate().expect("the enclave holds one identity");
}

fuzz_target!(|data: &[u8]| {
    RECIPIENT.with(|recipient| {
        // The input as a hostile seal: rejected or opened, never a crash.
        if let Some((encapsulation, rest)) = data.split_at_checked(ENCAPSULATION_BYTES) {
            if let Some((nonce, ciphertext)) = rest.split_at_checked(NONCE_BYTES) {
                let _ = recipient.open(encapsulation, nonce, ciphertext, &[]);
            }
        }

        // The input as a message: sealed to the recipient, it opens to exactly itself.
        let sealed = hybrid::seal(recipient.x25519_public(), recipient.mlkem768_public(), data, &[])
            .expect("a well-formed recipient can always be sealed to");
        let opened =
            recipient.open(&sealed.encapsulation, &sealed.nonce, &sealed.ciphertext, &[]).expect("a real seal opens");
        assert_eq!(opened.as_slice(), data);
    });
});
