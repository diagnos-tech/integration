//! 🇺🇸 The service account token (`dgn_sk1_…`, `docs/security/service-account-token.md` v3): one seed, four keys.
//!
//! A token is the service account's identity *and* the key to its share of
//! the vault: its 32-byte seed derives an Ed25519 + ML-DSA-65 pair that signs
//! every request and an X25519 + ML-KEM-768 pair that opens the session and
//! the group keys sealed to it. Classic and post-quantum together in both
//! roles, so a flaw in one algorithm — or a quantum computer one day — is not
//! enough. The seed enters this module once, from the pasted text, and from
//! then on only public keys and signatures come out.
//!
//! Layout: `codec` is the text form (spec §2); `keys` the derivation and the
//! hybrid signature (§3, §4); `python` the classes and functions Python sees.
//! Opening seals reuses `hybrid::Identity` (§5).
//!
//! 🇧🇷 O token de conta de serviço (`dgn_sk1_…`, `docs/security/service-account-token.md` v3): uma semente, quatro chaves.
//!
//! Um token é a identidade da conta de serviço *e* a chave da parte dela no
//! cofre: a semente de 32 bytes deriva um par Ed25519 + ML-DSA-65 que assina
//! toda requisição e um par X25519 + ML-KEM-768 que abre a sessão e as chaves
//! de grupo seladas para ele. Clássico e pós-quântico juntos nas duas funções,
//! para um defeito em um algoritmo — ou um computador quântico um dia — não
//! bastar. A semente entra neste módulo uma vez, do texto colado, e daí em
//! diante só saem chaves públicas e assinaturas.
//!
//! Organização: `codec` é a forma textual (spec §2); `keys` a derivação e a
//! assinatura híbrida (§3, §4); `python` as classes e funções que o Python
//! enxerga. Abrir selos reaproveita o `hybrid::Identity` (§5).

pub mod codec;
pub mod keys;
mod python;

pub use codec::{decode, encode, Decoded, TokenError, KEY_ID_BYTES, PREFIX, SEED_BYTES};
pub use keys::{derive, verify, Keys, MLDSA65_PUBLIC_BYTES, REQUEST_CONTEXT, SALT, SIGNATURE_BYTES};
pub use python::{decode_token, encode_token, verify_token_signature, TokenKeys};
