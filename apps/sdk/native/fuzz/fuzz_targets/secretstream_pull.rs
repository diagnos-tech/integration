//! `secretstream::pull` against any key, header and sequence of chunks: hostile chunks are rejected without
//! a panic, and every chunk pushed is pulled back unchanged, with its tag, in order.

#![no_main]

use _secure::secretstream::{self, HEADER_BYTES, KEY_BYTES, STATE_BYTES, TAG_FINAL, TAG_MESSAGE};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Some((key, rest)) = data.split_at_checked(KEY_BYTES) else { return };
    let Some((header, body)) = rest.split_at_checked(HEADER_BYTES) else { return };
    let chunks: Vec<&[u8]> = body.split(|&byte| byte == 0xff).collect();

    // The chunks as a hostile stream: each one rejected or opened, never a crash.
    let mut hostile = [0u8; STATE_BYTES];
    secretstream::init(&mut hostile, key, header).expect("a well-sized key and header always initialize");
    for chunk in &chunks {
        if secretstream::pull(&mut hostile, chunk, header).is_err() {
            break;
        }
    }

    // The same chunks as messages: what one side pushes, the other pulls back, tag included.
    let mut sender = [0u8; STATE_BYTES];
    let mut receiver = [0u8; STATE_BYTES];
    secretstream::init(&mut sender, key, header).expect("a well-sized key and header always initialize");
    secretstream::init(&mut receiver, key, header).expect("a well-sized key and header always initialize");
    for (index, message) in chunks.iter().enumerate() {
        let tag = if index + 1 == chunks.len() { TAG_FINAL } else { TAG_MESSAGE };
        let sealed = secretstream::push(&mut sender, message, header, tag).expect("any message can be pushed");
        let (opened, pulled) = secretstream::pull(&mut receiver, &sealed, header).expect("a pushed chunk pulls");
        assert_eq!((opened.as_slice(), pulled), (*message, tag));
    }
});
