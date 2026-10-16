"""🇺🇸 The contract's service account token and the RFC 9421 header matchers every interaction carries.

The token is built from fixed labels (`fixed_bytes`), never stored: the same
run produces the same token, and no key — real or fake — is written in this
repository. The headers are pinned by *shape*: `created` and `nonce` change
on every request by design, and the vault's provider verification replaces
`Signature-Input`/`Signature` (re-signing with a token its provider state
created, where the state needs a real key). What the contract fixes is the
profile (spec §4): the label `diagnos`, the exact component list of that
request, the parameter order, `keyid="svc_<32 hex>"`, `alg="ed25519+ml-dsa-65"`,
a 3373-byte signature in standard base64, and that no `Authorization`
header is sent.

🇧🇷 O token de conta de serviço do contrato e os matchers de header RFC 9421 que toda interação leva.

O token é montado de rótulos fixos (`fixed_bytes`), nunca guardado: a mesma
rodada produz o mesmo token, e nenhuma chave — real ou falsa — é escrita
neste repositório. Os headers são travados pela *forma*: `created` e `nonce`
mudam a cada requisição por desenho, e a verificação do provider no cofre
troca `Signature-Input`/`Signature` (reassinando com um token que o provider
state criou, onde o state precisa de chave de verdade). O que o contrato fixa
é o perfil (spec §4): o rótulo `diagnos`, a lista exata de componentes
daquela requisição, a ordem dos parâmetros, `keyid="svc_<32 hex>"`,
`alg="ed25519+ml-dsa-65"`, uma assinatura de 3373 bytes em base64 padrão, e
que nenhum header `Authorization` é enviado.
"""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Final, cast

from pact import match

from diagnos.crypto.secure import SecretBox
from diagnos.crypto.token_keys import encode_token
from diagnos.transport.message_signature import covered_components, signature_params
from diagnos.transport.service_token import DiagnosToken

from _crypto import b64url, fixed_bytes

WORKSPACE: Final = "ws-contract"
CREATED: Final = 1_780_000_000
KEY_ID: Final = f"svc_{fixed_bytes('token/key-id', 16).hex()}"
SIGNATURE_BYTES: Final = 64 + 3309


def token_text() -> str:
    """🇺🇸 The contract token's text — derived, never stored. 🇧🇷 O texto do token do contrato — derivado."""
    return encode_token(KEY_ID, SecretBox.from_bytes(bytearray(fixed_bytes("token/seed"))), WORKSPACE)


def token() -> DiagnosToken:
    """🇺🇸 The contract's token — a fresh object per call, since a test may wipe it.

    🇧🇷 O token do contrato — objeto novo por chamada, já que um teste pode apagá-lo.
    """
    return DiagnosToken.parse(token_text(), source="contract")


def identity_headers(*, query: bool = False, body: bool = False) -> dict[str, str]:
    """🇺🇸 `Signature-Input`/`Signature` (and `Content-Digest` with a body) for a request of this shape.

    🇧🇷 `Signature-Input`/`Signature` (e `Content-Digest` com corpo) para uma requisição desta forma.
    """
    components = covered_components(has_query=query, has_body=body)
    nonce = b64url(fixed_bytes("token/nonce", 16))
    example = signature_params(components, created=CREATED, keyid=KEY_ID, nonce=nonce)
    inner = re.escape(" ".join(f'"{component}"' for component in components))
    pattern = (
        rf'^diagnos=\({inner}\);created=[0-9]{{10}};keyid="svc_[0-9a-f]{{32}}";nonce="[A-Za-z0-9_-]{{22}}";'
        r'alg="ed25519\+ml-dsa-65"$'
    )
    signature = base64.b64encode(fixed_bytes("token/signature", SIGNATURE_BYTES)).decode()
    headers: dict[str, object] = {
        "Signature-Input": match.regex(f"diagnos={example}", regex=pattern),
        "Signature": match.regex(f"diagnos=:{signature}:", regex=r"^diagnos=:[A-Za-z0-9+/]{4498}==:$"),
    }
    if body:
        digest = base64.b64encode(hashlib.sha256(b"{}").digest()).decode()
        headers["Content-Digest"] = match.regex(f"sha-256=:{digest}:", regex=r"^sha-256=:[A-Za-z0-9+/]{43}=:$")
    return cast(dict[str, str], headers)
