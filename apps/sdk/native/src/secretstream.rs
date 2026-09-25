//! 🇺🇸 libsodium's `crypto_secretstream_xchacha20poly1305`, bit-exact, over a caller-owned 44-byte state.
//!
//! Drive bodies (`docs/PROTOCOL.md §9`) are written by PyNaCl/libsodium in
//! the web client and must open here, and vice versa. This is a faithful port
//! of `crypto_secretstream/xchacha20poly1305/secretstream_xchacha20poly1305.c`
//! built on RustCrypto's `chacha20` (IETF variant + HChaCha20) and `poly1305`,
//! rather than a dependency on a libsodium build: the state can then live
//! wherever the caller puts it — in this crate, a locked page — instead of
//! on the C heap.
//!
//! State layout, `[k 32 B][nonce 12 B]` where `nonce = [counter LE32][inonce 8 B]`,
//! is libsodium's own. Every function below takes that 44-byte slice.
//!
//! 🇧🇷 O `crypto_secretstream_xchacha20poly1305` do libsodium, bit a bit, sobre um estado de 44 bytes de quem chama.
//!
//! Corpos de drive (`docs/PROTOCOL.md §9`) são escritos pelo PyNaCl/libsodium
//! no client web e precisam abrir aqui, e vice-versa. Este é um porte fiel de
//! `crypto_secretstream/xchacha20poly1305/secretstream_xchacha20poly1305.c`
//! construído sobre o `chacha20` (variante IETF + HChaCha20) e o `poly1305`
//! do RustCrypto, em vez de uma dependência de um build do libsodium: o
//! estado pode então viver onde quem chama o puser — neste crate, numa página
//! travada — em vez de no heap do C.
//!
//! O layout do estado, `[k 32 B][nonce 12 B]` com `nonce = [contador LE32][inonce 8 B]`,
//! é o do próprio libsodium. Toda função abaixo recebe essa slice de 44 bytes.

use chacha20::cipher::{KeyIvInit, StreamCipher, StreamCipherSeek};
use chacha20::{hchacha, ChaCha20, Key, Nonce, R20};
use poly1305::universal_hash::{KeyInit, UniversalHash};
use poly1305::{Block as PolyBlock, Key as PolyKey, Poly1305, Tag};
use subtle::ConstantTimeEq;
use zeroize::Zeroizing;

use crate::error::{expect_len, Error};

/// 🇺🇸 Key length. 🇧🇷 Tamanho da chave.
pub const KEY_BYTES: usize = 32;
/// 🇺🇸 Header length (the random stream nonce). 🇧🇷 Tamanho do header (o nonce aleatório do stream).
pub const HEADER_BYTES: usize = 24;
/// 🇺🇸 Overhead per chunk: 1 tag byte + 16 MAC bytes. 🇧🇷 Overhead por chunk: 1 byte de tag + 16 de MAC.
pub const ABYTES: usize = 17;
/// 🇺🇸 `k ‖ nonce`. 🇧🇷 `k ‖ nonce`.
pub const STATE_BYTES: usize = KEY_BYTES + 12;

/// 🇺🇸 An ordinary chunk. 🇧🇷 Um chunk comum.
pub const TAG_MESSAGE: u8 = 0;
/// 🇺🇸 End of a logical message, stream continues. 🇧🇷 Fim de uma mensagem lógica, o stream continua.
pub const TAG_PUSH: u8 = 1;
/// 🇺🇸 Ratchets the key after this chunk. 🇧🇷 Rotaciona a chave depois deste chunk.
pub const TAG_REKEY: u8 = 2;
/// 🇺🇸 Last chunk of the stream. 🇧🇷 Último chunk do stream.
pub const TAG_FINAL: u8 = TAG_PUSH | TAG_REKEY;

const COUNTER_BYTES: usize = 4;
const INONCE_BYTES: usize = 8;
const BLOCK: usize = 64;

/// 🇺🇸 Derives the stream key from `key` and `header`, resetting the counter (init_push and init_pull are the same step).
/// 🇧🇷 Deriva a chave do stream de `key` e `header`, zerando o contador (init_push e init_pull são o mesmo passo).
pub fn init(state: &mut [u8], key: &[u8], header: &[u8]) -> Result<(), Error> {
    expect_len("secretstream state", state, STATE_BYTES)?;
    expect_len("secretstream key", key, KEY_BYTES)?;
    expect_len("secretstream header", header, HEADER_BYTES)?;
    let key: &Key = key.try_into().map_err(|_| Error::InvalidKey)?;
    let input = header[..16].try_into().map_err(|_| Error::InvalidKey)?;
    let subkey = Zeroizing::new(hchacha::<R20>(key, input));
    let (k, nonce) = state.split_at_mut(KEY_BYTES);
    k.copy_from_slice(subkey.as_ref());
    nonce[..COUNTER_BYTES].copy_from_slice(&1u32.to_le_bytes());
    nonce[COUNTER_BYTES..].copy_from_slice(&header[16..]);
    Ok(())
}

/// 🇺🇸 ChaCha20-IETF keystream at 64-byte block `index`, XORed into (`xor`) or written over `buf`.
/// 🇧🇷 Keystream ChaCha20-IETF no bloco de 64 bytes `index`, XORado em (`xor`) ou escrito sobre `buf`.
fn keystream(k: &[u8], nonce: &[u8], index: u32, buf: &mut [u8], xor: bool) -> Result<(), Error> {
    let key: &Key = k.try_into().map_err(|_| Error::InvalidKey)?;
    let nonce: &Nonce = nonce.try_into().map_err(|_| Error::InvalidKey)?;
    let mut cipher = ChaCha20::new(key, nonce);
    cipher.seek(u64::from(index) * BLOCK as u64);
    if xor {
        cipher.apply_keystream(buf);
    } else {
        cipher.write_keystream(buf);
    }
    Ok(())
}

/// 🇺🇸 Poly1305 fed as one continuous byte stream, exactly as `crypto_onetimeauth_poly1305_update` is.
///
/// libsodium pads the ciphertext with `mlen & 0xf` zero bytes — not up to
/// the next 16-byte boundary — a historical quirk frozen into the format.
/// The segments therefore do not align to blocks, so the MAC has to see the
/// bytes as a stream and let Poly1305's own final-block padding handle the
/// tail. Padding every segment to a block (`universal_hash::update_padded`)
/// would be a different, incompatible MAC.
///
/// 🇧🇷 Poly1305 alimentado como um único stream de bytes, exatamente como `crypto_onetimeauth_poly1305_update` é.
///
/// O libsodium preenche o ciphertext com `mlen & 0xf` bytes zero — não até a
/// próxima fronteira de 16 bytes — uma peculiaridade histórica congelada no
/// formato. Os segmentos portanto não se alinham a blocos, então o MAC
/// precisa ver os bytes como stream e deixar o próprio padding de bloco final
/// do Poly1305 cuidar da cauda. Preencher cada segmento até um bloco
/// (`universal_hash::update_padded`) seria um MAC diferente, incompatível.
struct Mac {
    poly: Poly1305,
    pending: Zeroizing<Vec<u8>>,
}

impl Mac {
    fn over(k: &[u8], nonce: &[u8]) -> Result<Self, Error> {
        let mut block = Zeroizing::new([0u8; BLOCK]);
        keystream(k, nonce, 0, &mut block[..], false)?;
        let key: &PolyKey = block[..32].try_into().map_err(|_| Error::InvalidKey)?;
        Ok(Self { poly: Poly1305::new(key), pending: Zeroizing::new(Vec::with_capacity(16)) })
    }

    fn update(&mut self, data: &[u8]) {
        let mut data = data;
        if !self.pending.is_empty() {
            let take = (16 - self.pending.len()).min(data.len());
            self.pending.extend_from_slice(&data[..take]);
            data = &data[take..];
            if self.pending.len() == 16 {
                let block: &PolyBlock = self.pending[..].try_into().expect("pending holds exactly one block");
                self.poly.update(std::slice::from_ref(block));
                self.pending.clear();
            }
        }
        let (blocks, tail) = PolyBlock::slice_as_chunks(data);
        self.poly.update(blocks);
        self.pending.extend_from_slice(tail);
    }

    fn zeros(&mut self, count: usize) {
        self.update(&[0u8; 16][..count]);
    }

    fn finalize(self) -> Tag {
        self.poly.compute_unpadded(&self.pending)
    }
}

fn lengths(ad_len: usize, body_len: usize) -> [u8; 16] {
    let mut out = [0u8; 16];
    out[..8].copy_from_slice(&(ad_len as u64).to_le_bytes());
    out[8..].copy_from_slice(&(body_len as u64).to_le_bytes());
    out
}

fn ratchet(state: &mut [u8], mac: &[u8], tag: u8) -> Result<(), Error> {
    let (k, nonce) = state.split_at_mut(KEY_BYTES);
    for (n, m) in nonce[COUNTER_BYTES..].iter_mut().zip(&mac[..INONCE_BYTES]) {
        *n ^= *m;
    }
    let mut counter = [0u8; COUNTER_BYTES];
    counter.copy_from_slice(&nonce[..COUNTER_BYTES]);
    let next = u32::from_le_bytes(counter).wrapping_add(1);
    nonce[..COUNTER_BYTES].copy_from_slice(&next.to_le_bytes());
    if tag & TAG_REKEY != 0 || next == 0 {
        rekey(k, nonce)?;
    }
    Ok(())
}

fn rekey(k: &mut [u8], nonce: &mut [u8]) -> Result<(), Error> {
    let mut next = Zeroizing::new([0u8; KEY_BYTES + INONCE_BYTES]);
    next[..KEY_BYTES].copy_from_slice(k);
    next[KEY_BYTES..].copy_from_slice(&nonce[COUNTER_BYTES..]);
    keystream(k, nonce, 0, &mut next[..], true)?;
    k.copy_from_slice(&next[..KEY_BYTES]);
    nonce[COUNTER_BYTES..].copy_from_slice(&next[KEY_BYTES..]);
    nonce[..COUNTER_BYTES].copy_from_slice(&1u32.to_le_bytes());
    Ok(())
}

/// 🇺🇸 Encrypts one chunk: `tag_byte ‖ ciphertext ‖ mac` (`message.len() + ABYTES` bytes).
/// 🇧🇷 Cifra um chunk: `byte_de_tag ‖ ciphertext ‖ mac` (`message.len() + ABYTES` bytes).
pub fn push(state: &mut [u8], message: &[u8], ad: &[u8], tag: u8) -> Result<Vec<u8>, Error> {
    expect_len("secretstream state", state, STATE_BYTES)?;
    let (k, nonce) = state.split_at(KEY_BYTES);
    let mut mac = Mac::over(k, nonce)?;

    let mut block = Zeroizing::new([0u8; BLOCK]);
    block[0] = tag;
    keystream(k, nonce, 1, &mut block[..], true)?;
    mac.update(ad);
    mac.zeros((0x10 - ad.len()) & 0xf);
    mac.update(&block[..]);

    let mut out = Vec::with_capacity(message.len() + ABYTES);
    out.push(block[0]);
    out.extend_from_slice(message);
    keystream(k, nonce, 2, &mut out[1..], true)?;
    mac.update(&out[1..]);
    mac.zeros(message.len() & 0xf);
    mac.update(&lengths(ad.len(), BLOCK + message.len()));
    let mac = mac.finalize();
    out.extend_from_slice(mac.as_ref());

    ratchet(state, mac.as_ref(), tag)?;
    Ok(out)
}

/// 🇺🇸 Authenticates and decrypts one chunk, returning `(message, tag)`; any failure is `DidNotOpen`.
/// 🇧🇷 Autentica e decifra um chunk, devolvendo `(mensagem, tag)`; toda falha é `DidNotOpen`.
pub fn pull(state: &mut [u8], input: &[u8], ad: &[u8]) -> Result<(Vec<u8>, u8), Error> {
    expect_len("secretstream state", state, STATE_BYTES)?;
    if input.len() < ABYTES {
        return Err(Error::DidNotOpen);
    }
    let body_len = input.len() - ABYTES;
    let (k, nonce) = state.split_at(KEY_BYTES);
    let mut mac = Mac::over(k, nonce)?;

    let mut block = Zeroizing::new([0u8; BLOCK]);
    block[0] = input[0];
    keystream(k, nonce, 1, &mut block[..], true)?;
    let tag = block[0];
    block[0] = input[0];
    mac.update(ad);
    mac.zeros((0x10 - ad.len()) & 0xf);
    mac.update(&block[..]);

    let ciphertext = &input[1..=body_len];
    let stored_mac = &input[1 + body_len..];
    mac.update(ciphertext);
    mac.zeros(body_len & 0xf);
    mac.update(&lengths(ad.len(), BLOCK + body_len));
    let computed = mac.finalize();
    let computed: &[u8] = computed.as_ref();
    if !bool::from(computed.ct_eq(stored_mac)) {
        return Err(Error::DidNotOpen);
    }

    let mut message = ciphertext.to_vec();
    keystream(k, nonce, 2, &mut message, true)?;
    ratchet(state, stored_mac, tag)?;
    Ok((message, tag))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_across_chunks_with_rekey_and_final() {
        let key = [3u8; KEY_BYTES];
        let header = [5u8; HEADER_BYTES];
        let mut push_state = [0u8; STATE_BYTES];
        let mut pull_state = [0u8; STATE_BYTES];
        init(&mut push_state, &key, &header).unwrap();
        init(&mut pull_state, &key, &header).unwrap();

        let chunks: [(&[u8], u8); 4] =
            [(b"one", TAG_MESSAGE), (b"", TAG_REKEY), (b"three", TAG_PUSH), (b"last", TAG_FINAL)];
        for (message, tag) in chunks {
            let sealed = push(&mut push_state, message, b"ad", tag).unwrap();
            assert_eq!(sealed.len(), message.len() + ABYTES);
            let (opened, got_tag) = pull(&mut pull_state, &sealed, b"ad").unwrap();
            assert_eq!(opened, message);
            assert_eq!(got_tag, tag);
        }
        assert_eq!(push_state, pull_state);
    }

    #[test]
    fn tamper_and_reorder_fail() {
        let key = [3u8; KEY_BYTES];
        let header = [5u8; HEADER_BYTES];
        let mut push_state = [0u8; STATE_BYTES];
        init(&mut push_state, &key, &header).unwrap();
        let first = push(&mut push_state, b"first", b"", TAG_MESSAGE).unwrap();
        let second = push(&mut push_state, b"second", b"", TAG_MESSAGE).unwrap();

        let mut pull_state = [0u8; STATE_BYTES];
        init(&mut pull_state, &key, &header).unwrap();
        assert_eq!(pull(&mut pull_state, &second, b"").unwrap_err(), Error::DidNotOpen);

        let mut tampered = first.clone();
        tampered[2] ^= 1;
        assert_eq!(pull(&mut pull_state, &tampered, b"").unwrap_err(), Error::DidNotOpen);
        assert_eq!(pull(&mut pull_state, &first[..ABYTES - 1], b"").unwrap_err(), Error::DidNotOpen);
        assert!(pull(&mut pull_state, &first, b"").is_ok());
    }
}
