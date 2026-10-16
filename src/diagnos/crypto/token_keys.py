"""🇺🇸 The service account token's cryptography, run in the enclave: decode, derive, sign (spec §2–§4).

`decode_token` turns the pasted text into a key id, a workspace id and a
`SecretBox` holding the 32-byte seed — the seed goes from the text straight
into locked memory, in Rust, and never exists as Python `bytes`.
`TokenKeys.from_seed` derives the four key pairs inside the enclave; what
comes back to Python is public keys and signatures, nothing else.

🇧🇷 A criptografia do token de conta de serviço, rodada no enclave: decodificar, derivar, assinar (spec §2–§4).

`decode_token` transforma o texto colado num id de chave, um id de workspace
e um `SecretBox` com a semente de 32 bytes — a semente vai do texto direto
para memória travada, em Rust, e nunca existe como `bytes` do Python.
`TokenKeys.from_seed` deriva os quatro pares dentro do enclave; o que volta ao
Python são chaves públicas e assinaturas, nada mais.
"""

from __future__ import annotations

from typing import Final, Literal

from diagnos import _secure

from .secure import SecretBox

TokenKeys = _secure.TokenKeys
"""🇺🇸 The four key pairs of one seed, private halves locked. 🇧🇷 Os quatro pares de uma semente, privadas travadas."""

PREFIX: Final = _secure.TOKEN_PREFIX
KEY_ID_BYTES: Final = _secure.TOKEN_KEY_ID_BYTES
SEED_BYTES: Final = _secure.TOKEN_SEED_BYTES
SIGNATURE_BYTES: Final = _secure.TOKEN_SIGNATURE_BYTES
MLDSA65_PUBLIC_BYTES: Final = _secure.MLDSA65_PUBLIC_BYTES

DecodeFailure = Literal["prefix", "encoding", "length", "checksum", "workspace"]
"""🇺🇸 Why a text is not a token — the reference's `reason` codes. 🇧🇷 Por que não é token — os `reason` da referência."""

_FAILURES: Final[frozenset[str]] = frozenset({"prefix", "encoding", "length", "checksum", "workspace"})


def decode_token(text: str) -> tuple[str, SecretBox, str] | DecodeFailure:
    """🇺🇸 `(svc_<hex>, seed box, workspace_id)`, or the failure code — returned, never raised.

    Returning the code instead of raising keeps this frame (which holds the
    token text) out of every traceback; the caller deletes its own copy and
    only then raises.

    🇧🇷 `(svc_<hex>, caixa da semente, workspace_id)`, ou o código da falha — devolvido, nunca lançado.

    Devolver o código em vez de lançar mantém este quadro (que guarda o texto
    do token) fora de todo traceback; quem chama apaga a própria cópia e só
    então lança.
    """
    try:
        key_id, seed, workspace_id = _secure.decode_token(text)
    except ValueError as exc:
        code = str(exc)
        del text
        return code if code in _FAILURES else "encoding"  # type: ignore[return-value]
    return f"svc_{key_id.hex()}", seed, workspace_id


def encode_token(key_id: str, seed: SecretBox, workspace_id: str) -> str:
    """🇺🇸 The text of a token — for tests and tooling; real tokens are minted once, in the browser.

    🇧🇷 O texto de um token — para testes e ferramentas; tokens reais nascem uma vez, no navegador.
    """
    return _secure.encode_token(bytes.fromhex(key_id.removeprefix("svc_")), seed, workspace_id)


def verify_signature(ed25519_public: bytes, mldsa65_public: bytes, message: bytes, signature: bytes) -> bool:
    """🇺🇸 What the vault checks: both halves valid. For test doubles. 🇧🇷 O que o cofre confere: as duas metades."""
    return _secure.verify_token_signature(ed25519_public, mldsa65_public, message, signature)
