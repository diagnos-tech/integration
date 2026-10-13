//! 🇺🇸 secretstream with associated data of any length, found by `fuzz/fuzz_targets/secretstream_pull.rs`: AD
//! longer than one Poly1305 block used to overflow the padding arithmetic and panic.
//!
//! 🇧🇷 secretstream com dados associados de qualquer tamanho, achado pelo `fuzz/fuzz_targets/secretstream_pull.rs`:
//! um AD maior que um bloco do Poly1305 estourava a aritmética do padding e entrava em pânico.

use _secure::secretstream::{self, HEADER_BYTES, KEY_BYTES, STATE_BYTES, TAG_FINAL, TAG_MESSAGE};

fn pair() -> ([u8; STATE_BYTES], [u8; STATE_BYTES]) {
    let (key, header) = ([9u8; KEY_BYTES], [4u8; HEADER_BYTES]);
    let (mut sender, mut receiver) = ([0u8; STATE_BYTES], [0u8; STATE_BYTES]);
    secretstream::init(&mut sender, &key, &header).unwrap();
    secretstream::init(&mut receiver, &key, &header).unwrap();
    (sender, receiver)
}

#[test]
fn associated_data_of_every_length_round_trips() {
    for ad_len in [0, 1, 15, 16, 17, 24, 31, 32, 33, 64, 100] {
        let ad = vec![0xa5u8; ad_len];
        let (mut sender, mut receiver) = pair();
        for (message, tag) in [(&b"first"[..], TAG_MESSAGE), (&b"last chunk"[..], TAG_FINAL)] {
            let sealed = secretstream::push(&mut sender, message, &ad, tag).unwrap();
            let (opened, pulled) = secretstream::pull(&mut receiver, &sealed, &ad).unwrap();
            assert_eq!((opened.as_slice(), pulled), (message, tag), "ad_len = {ad_len}");
        }
    }
}

#[test]
fn associated_data_is_authenticated() {
    let (mut sender, mut receiver) = pair();
    let sealed = secretstream::push(&mut sender, b"payload", &[1u8; 40], TAG_MESSAGE).unwrap();
    assert!(secretstream::pull(&mut receiver, &sealed, &[2u8; 40]).is_err());
}
