"""🇺🇸 RFC 9421 request signatures: the published Ed25519 example, and a vector built by hand in the test.

Two independent checks. The first signs RFC 9421 Appendix B.2.6's own
signature base with the RFC's Ed25519 test key and must reproduce the
signature printed in the RFC, byte for byte — the enclave and the base64
framing against the standard. The second writes the signature base the
vault must rebuild *by hand*, line by line, and verifies the SDK's
`Signature` against it with PyNaCl — the SDK's base construction against
the service account credential spec (§3).

🇧🇷 Assinaturas de requisição RFC 9421: o exemplo Ed25519 publicado, e um vetor montado à mão no teste.

Duas conferências independentes. A primeira assina a própria signature base
do Apêndice B.2.6 da RFC 9421 com a chave de teste Ed25519 da RFC e precisa
reproduzir a assinatura impressa na RFC, byte a byte — o enclave e o
enquadramento base64 contra o padrão. A segunda escreve *à mão*, linha a
linha, a signature base que o cofre precisa remontar, e verifica o
`Signature` do SDK contra ela com o PyNaCl — a montagem da base do SDK
contra a spec da credencial de conta de serviço (§3).
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets

import httpx
from nacl.signing import SigningKey, VerifyKey

from diagnos.crypto import ed25519
from diagnos.crypto.encoding import b64url_decode, b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.transport.credential import ServiceAccountCredential
from diagnos.transport.message_signature import content_digest, identity_headers, signature_base

# 🇺🇸 RFC 9421 Appendix B.1.4 (`test-key-ed25519`, the JWK `d`), published test material, and B.2.6's signature.
# 🇧🇷 RFC 9421 Apêndice B.1.4 (`test-key-ed25519`, o `d` do JWK), material de teste público, e a assinatura do B.2.6.
RFC9421_B14_D = "n4Ni-HpISpVObnQMW0wOhCKROaIKqKtW_2ZYb2p9KcU"
RFC9421_B14_X = "JrQLj5P_89iXES9-vFgrIy29clF9CC_oPPsw3c5D0bs"
RFC9421_B26_BASE = "\n".join(
    [
        '"date": Tue, 20 Apr 2021 02:07:55 GMT',
        '"@method": POST',
        '"@path": /foo',
        '"@authority": example.com',
        '"content-type": application/json',
        '"content-length": 18',
        '"@signature-params": ("date" "@method" "@path" "@authority" "content-type" "content-length")'
        ';created=1618884473;keyid="test-key-ed25519"',
    ]
)
RFC9421_B26_SIG = "wqcAqbmYJ2ji2glfAMaRy4gruYYnx2nEFN2HN6jrnDnQCK1u02Gb04v9EDgwUPiu4A0w6vuQv5lIp5WPpBKRCw=="


def test_the_enclave_reproduces_rfc9421_appendix_b26() -> None:
    """🇺🇸 Same public key, same signature as the RFC prints. 🇧🇷 Mesma chave pública e assinatura que a RFC imprime."""
    seed = SecretBox.from_bytes(bytearray(b64url_decode(RFC9421_B14_D)))
    assert b64url_encode(ed25519.public_key(seed)) == RFC9421_B14_X
    assert base64.b64encode(ed25519.sign(seed, RFC9421_B26_BASE.encode())).decode() == RFC9421_B26_SIG


def _credential() -> tuple[ServiceAccountCredential, bytes]:
    """🇺🇸 A credential generated now, plus its seed for the oracle. 🇧🇷 Uma credencial gerada agora, mais a semente."""
    seed = secrets.token_bytes(32)
    identity = f"svc_{secrets.token_hex(16)}@wsVector.diagnos.health"
    return ServiceAccountCredential.parse(f"{identity}:{b64url_encode(seed)}"), seed


def _signature_bytes(header: str) -> bytes:
    """🇺🇸 `diagnos=:<base64>:` → raw bytes. 🇧🇷 `diagnos=:<base64>:` → bytes crus."""
    match = re.fullmatch(r"diagnos=:([A-Za-z0-9+/]+={0,2}):", header)
    assert match is not None, header
    return base64.b64decode(match[1])


def test_a_post_with_query_and_body_signs_the_base_the_vault_rebuilds() -> None:
    """🇺🇸 The hand-written base for `POST …?b=2&a=1` with a JSON body verifies under the credential's key.

    🇧🇷 A base escrita à mão para `POST …?b=2&a=1` com corpo JSON verifica sob a chave da credencial.
    """
    credential, seed = _credential()
    body = b'{"name":"Ana","note":"caf\xc3\xa9"}'
    url = httpx.URL("https://vault.example/api/external/v1/workspaces/wsVector/patients?b=2&a=%2F1")
    headers = credential.request_headers("post", url, body, 1_760_000_000)

    nonce = re.search(r';nonce="([A-Za-z0-9_-]{22})";', headers["Signature-Input"])
    assert nonce is not None
    digest = "sha-256=:" + base64.b64encode(hashlib.sha256(body).digest()).decode() + ":"
    params = (
        '("@method" "@path" "@query" "content-digest");created=1760000000;'
        f'keyid="{credential.identity}";nonce="{nonce[1]}";alg="ed25519"'
    )
    expected_base = (
        '"@method": POST\n'
        '"@path": /api/external/v1/workspaces/wsVector/patients\n'
        '"@query": ?b=2&a=%2F1\n'
        f'"content-digest": {digest}\n'
        f'"@signature-params": {params}'
    )
    assert headers["Signature-Input"] == f"diagnos={params}"
    assert headers["Content-Digest"] == digest
    assert "Authorization" not in headers
    VerifyKey(bytes(SigningKey(seed).verify_key)).verify(expected_base.encode(), _signature_bytes(headers["Signature"]))


def test_a_get_without_query_covers_only_method_and_path() -> None:
    """🇺🇸 No query, no body: no `@query`, no `content-digest`, no `Content-Digest` header.

    🇧🇷 Sem query, sem corpo: sem `@query`, sem `content-digest`, sem header `Content-Digest`.
    """
    credential, seed = _credential()
    url = httpx.URL("https://vault.example/api/external/v1/session/lock")
    headers = credential.request_headers("GET", url, b"", 1_760_000_001)
    assert headers["Signature-Input"].startswith('diagnos=("@method" "@path");created=1760000001;keyid="svc_')
    assert headers["Signature-Input"].endswith(';alg="ed25519"')
    assert "Content-Digest" not in headers
    params = headers["Signature-Input"].removeprefix("diagnos=")
    base = f'"@method": GET\n"@path": /api/external/v1/session/lock\n"@signature-params": {params}'
    VerifyKey(bytes(SigningKey(seed).verify_key)).verify(base.encode(), _signature_bytes(headers["Signature"]))


def test_every_attempt_gets_a_fresh_nonce_and_signature() -> None:
    """🇺🇸 Two calls with identical inputs never share a nonce — a retry is never a replay.

    🇧🇷 Duas chamadas com entradas idênticas nunca dividem um nonce — retentar nunca é replay.
    """
    credential, _ = _credential()
    url = httpx.URL("https://vault.example/x")
    first = credential.request_headers("POST", url, b"{}", 1)
    second = credential.request_headers("POST", url, b"{}", 1)
    assert first["Signature-Input"] != second["Signature-Input"]
    assert first["Signature"] != second["Signature"]


def test_building_blocks_match_rfc9530_and_rfc9421_framing() -> None:
    """🇺🇸 `Content-Digest` of an empty body; a base with a query, no body. 🇧🇷 Digest vazio; base com query."""
    assert content_digest(b"") == "sha-256=:47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=:"
    base = signature_base(method="get", path="/p", query="x=1", digest=None, params="()")
    assert base == '"@method": GET\n"@path": /p\n"@query": ?x=1\n"@signature-params": ()'
    headers = identity_headers(
        lambda message: b"\x00" * 64, keyid="k", method="GET", url=httpx.URL("/p"), body=b"", created=5, nonce="n"
    )
    assert headers == {
        "Signature-Input": 'diagnos=("@method" "@path");created=5;keyid="k";nonce="n";alg="ed25519"',
        "Signature": "diagnos=:" + base64.b64encode(b"\x00" * 64).decode() + ":",
    }
