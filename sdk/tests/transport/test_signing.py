"""🇺🇸 `canonical_string`/`sign_canonical` reproduce the vault's own vector exactly.

Any drift here is silent in dev (both ends of a mismatched pair still return
*a* string) and only shows up as a `401 SignatureInvalid` against the real
vault, so this test pins the whole pipeline against
`tests/vectors/request_signature.json`, generated from the TypeScript
reference — not against our own understanding of the spec.

🇧🇷 `canonical_string`/`sign_canonical` reproduzem o vetor do próprio cofre, ao pé da letra.

Qualquer desvio aqui é silencioso em dev (os dois lados de um par
descasado ainda devolvem *uma* string) e só aparece como `401
SignatureInvalid` contra o cofre de verdade, então este teste trava o
pipeline inteiro contra `tests/vectors/request_signature.json`, gerado da
referência em TypeScript — não contra nosso próprio entendimento da spec.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from conftest import VECTORS
from diagnos.crypto.encoding import b64url_decode
from diagnos.transport.signing import canonical_string, normalize_query, sign_canonical


def _load_vector() -> dict[str, Any]:
    """🇺🇸 Reads and parses `request_signature.json`. 🇧🇷 Lê e faz o parse de `request_signature.json`."""
    return json.loads((VECTORS / "request_signature.json").read_text())


def test_canonical_string_matches_vector() -> None:
    """🇺🇸 The six fields join into exactly the vector's `canonical_string`.

    🇧🇷 Os seis campos se juntam exatamente no `canonical_string` do vetor.
    """
    vector = _load_vector()
    body = vector["body_utf8"].encode("utf-8")
    result = canonical_string(
        vector["method"],
        vector["path"],
        vector["raw_query"],
        vector["timestamp"],
        vector["nonce"],
        body,
    )
    assert result == vector["canonical_string"]


def test_canonical_string_uppercases_method() -> None:
    """🇺🇸 A lowercase `method` still produces the vector's uppercase `METHOD` field.

    🇧🇷 Um `method` minúsculo ainda produz o campo `METHOD` maiúsculo do vetor.
    """
    vector = _load_vector()
    body = vector["body_utf8"].encode("utf-8")
    lower = canonical_string(
        vector["method"].lower(),
        vector["path"],
        vector["raw_query"],
        vector["timestamp"],
        vector["nonce"],
        body,
    )
    assert lower == vector["canonical_string"]


def test_body_digest_matches_vector() -> None:
    """🇺🇸 `sha256(body)` matches the vector's precomputed digest.

    🇧🇷 `sha256(body)` bate com o digest pré-computado do vetor.
    """
    vector = _load_vector()
    digest = hashlib.sha256(vector["body_utf8"].encode("utf-8")).hexdigest()
    assert digest == vector["body_sha256_hex"]


def test_empty_body_digest_matches_vector() -> None:
    """🇺🇸 An empty body hashes to `sha256("")`, per `docs/PROTOCOL.md §3`.

    🇧🇷 Corpo vazio vira `sha256("")`, conforme `docs/PROTOCOL.md §3`.
    """
    vector = _load_vector()
    assert hashlib.sha256(b"").hexdigest() == vector["empty_body_sha256_hex"]


def test_sign_canonical_matches_vector() -> None:
    """🇺🇸 HMAC-SHA512 of the vector's canonical string matches its precomputed hex.

    🇧🇷 HMAC-SHA512 da string canônica do vetor bate com o hex pré-computado.
    """
    vector = _load_vector()
    sign_key = b64url_decode(vector["sign_key_b64url"])
    signature = sign_canonical(sign_key, vector["canonical_string"])
    assert signature == vector["hmac_sha512_hex"]


def test_normalize_query_sorts_raw_pairs_by_code_point() -> None:
    """🇺🇸 Raw `k=v` pairs sort by code point, matching the vector's `QUERY` field.

    🇧🇷 Pares `k=v` crus ordenam por ponto de código, batendo com o campo `QUERY` do vetor.
    """
    # 🇺🇸 Vector's own query, unsorted input, expected output from the canonical string.
    # 🇧🇷 A própria query do vetor, entrada desordenada, saída esperada da string canônica.
    assert normalize_query("limit=10&cursor=abc%3D&a=1") == "a=1&cursor=abc%3D&limit=10"


def test_normalize_query_empty_string_stays_empty() -> None:
    """🇺🇸 No query means the canonical `QUERY` field is the empty string.

    🇧🇷 Sem query, o campo `QUERY` canônico é a string vazia.
    """
    assert normalize_query("") == ""


def test_normalize_query_repeated_keys_and_percent_encoding_untouched() -> None:
    """🇺🇸 Repeated keys sort as opaque strings; percent-encoding is never decoded.

    🇧🇷 Chaves repetidas ordenam como strings opacas; percent-encoding nunca é decodificado.
    """
    # 🇺🇸 Two pairs with the same key are sorted as opaque strings, and a
    # percent-encoded space (`ws%201`) is never decoded — decoding here would
    # let two different raw queries collide into the same canonical string.
    # 🇧🇷 Dois pares com a mesma chave são ordenados como strings opacas, e um
    # espaço percent-encoded (`ws%201`) nunca é decodificado — decodificar
    # aqui deixaria duas queries cruas diferentes colidirem na mesma string
    # canônica.
    raw_query = "tag=b&name=ws%201&tag=a"
    assert normalize_query(raw_query) == "name=ws%201&tag=a&tag=b"
