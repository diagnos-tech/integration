"""🇺🇸 The request signature — mirrors the vault's canonical string byte for byte.

The vault reconstructs the canonical string from the raw request it received;
any byte this module normalizes differently is an invisible `401
SignatureInvalid` on the caller's side with nothing to grep for. Every
ambiguity below is resolved the way the TypeScript reference resolves it,
never left to "seems reasonable." The HMAC itself runs inside the enclave:
the `sign_key` is a `SecretBox` and never becomes Python `bytes`.

🇧🇷 A assinatura da requisição — espelha a string canônica do cofre
byte a byte.

O cofre reconstrói a string canônica a partir da requisição crua que
recebeu; qualquer byte que este módulo normalizar diferente é um `401
SignatureInvalid` invisível do lado de quem chamou, sem nada para grepar.
Toda ambiguidade abaixo é resolvida do jeito que a referência em TypeScript
resolve, nunca deixada em "parece razoável". O HMAC em si roda dentro do
enclave: o `sign_key` é um `SecretBox` e nunca vira `bytes` do Python.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable

import httpx

from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretLike, as_secret

# 🇺🇸 16 bytes matches the vault's own minimum (`docs/PROTOCOL.md §3`); more would
# just be a longer header for no extra uniqueness the OS RNG doesn't already give.
# 🇧🇷 16 bytes casa com o mínimo do próprio cofre (`docs/PROTOCOL.md §3`); mais seria
# só um header maior sem unicidade extra que o RNG do SO já não dê.
NONCE_BYTES = 16


def normalize_query(raw_query: str) -> str:
    """🇺🇸 Sort the raw (still percent-encoded) `k=v` pairs by code point.

    Sorting the raw pairs *before* any decoding is the part that matters: two
    clients that emit the same parameters in a different order (routine
    across `URLSearchParams` implementations in different languages) land on
    the same canonical `QUERY` without either one needing to agree on
    insertion order.

    🇧🇷 Ordena os pares `k=v` crus (ainda percent-encoded) por ponto de código.

    Ordenar os pares crus *antes* de qualquer decodificação é o que importa:
    dois clientes que emitem os mesmos parâmetros em ordem diferente (comum
    entre implementações de `URLSearchParams` em linguagens diferentes) caem
    no mesmo `QUERY` canônico sem que nenhum dos dois precise concordar sobre
    ordem de inserção.
    """
    if raw_query == "":
        return ""
    return "&".join(sorted(raw_query.split("&")))


def canonical_string(
    method: str,
    path: str,
    raw_query: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    r"""🇺🇸 The six-field, `\n`-joined string HMAC-SHA512 is computed over.

    `path` is used exactly as it goes on the wire — percent-encoded, never
    decoded — because decoding before signing reopens the classic "path
    confusion" ambiguity (`%2F` vs `/`, hex case) between what the caller
    signed and what the server's router ends up serving. An empty body
    hashes to SHA-256 of the empty string, not a special-cased empty field,
    so "no body" and "an explicit zero-byte body" are always the same value.

    🇧🇷 A string de seis campos unidos por `\n` sobre a qual roda o HMAC-SHA512.

    `path` é usado exatamente como vai no fio — percent-encoded, nunca
    decodificado — porque decodificar antes de assinar reabre a ambiguidade
    clássica de "path confusion" (`%2F` vs `/`, caixa do hex) entre o que
    quem chamou assinou e o que o roteador do servidor acaba servindo. Corpo
    vazio vira o SHA-256 da string vazia, não um campo vazio especial, então
    "sem corpo" e "corpo de zero bytes explícito" são sempre o mesmo valor.
    """
    body_digest = hashlib.sha256(body).hexdigest()
    return "\n".join(
        [
            method.upper(),
            path,
            normalize_query(raw_query),
            timestamp,
            nonce,
            body_digest,
        ]
    )


def sign_canonical(sign_key: SecretLike, canonical: str) -> str:
    """🇺🇸 HMAC-SHA512 over the canonical string, UTF-8 encoded, hex digest (lowercase), computed inside the enclave.

    🇧🇷 HMAC-SHA512 sobre a string canônica, codificada em UTF-8, digest em hex (minúsculo), calculado dentro do enclave.
    """
    return as_secret(sign_key).hmac_sha512(canonical.encode("utf-8")).hex()


def signature_headers(
    sign_key: SecretLike,
    *,
    method: str,
    url: httpx.URL,
    body: bytes,
    timestamp: int,
    nonce: str,
) -> dict[str, str]:
    """🇺🇸 Build the three `X-Signature-*` headers for one request.

    `url.raw_path` is httpx's undecoded path+query exactly as it will be
    written to the socket — the same bytes the vault's own HTTP parser sees —
    so splitting it on the first `?` gives `PATH` and `QUERY` with no
    re-encoding step of our own to drift from the server's.

    🇧🇷 Monta os três headers `X-Signature-*` de uma requisição.

    `url.raw_path` é o path+query não decodificado do httpx, exatamente como
    vai ser escrito no socket — os mesmos bytes que o parser HTTP do cofre
    vê — então dividir no primeiro `?` dá `PATH` e `QUERY` sem nenhum passo
    de re-encoding nosso para divergir do servidor.
    """
    path, _, raw_query = url.raw_path.decode("ascii").partition("?")
    timestamp_text = str(timestamp)
    canonical = canonical_string(method, path, raw_query, timestamp_text, nonce, body)
    return {
        "X-Signature-Timestamp": timestamp_text,
        "X-Signature-Nonce": nonce,
        "X-Signature-Hmac": sign_canonical(sign_key, canonical),
    }


def new_nonce(random: Callable[[int], bytes] = secrets.token_bytes) -> str:
    """🇺🇸 A fresh `(timestamp, nonce)` half: 16 random bytes, b64url.

    The vault treats `(timestamp, nonce)` as single-use (`409 ReplayDetected`
    on a byte-identical resend, `docs/PROTOCOL.md §3`), so every signed
    attempt — including retries — calls this again rather than reusing one.

    🇧🇷 Metade de um `(timestamp, nonce)` novo: 16 bytes aleatórios, b64url.

    O cofre trata `(timestamp, nonce)` como uso único (`409 ReplayDetected`
    num reenvio idêntico, `docs/PROTOCOL.md §3`), então toda tentativa
    assinada — inclusive retentativas — chama isto de novo em vez de reusar.
    """
    return b64url_encode(random(NONCE_BYTES))
