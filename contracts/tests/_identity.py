"""🇺🇸 The contract's service account credential and the RFC 9421 header matchers every interaction carries.

The credential is derived from fixed labels (`fixed_bytes`), never stored:
the same run produces the same identity, and no key — real or fake — is
written in this repository. The headers are pinned by *shape*: `created`
and `nonce` change on every request by design, so the vault's provider
verification re-signs each replayed request with a key it seeded itself
(its request filter replaces `Signature-Input`/`Signature`, keeping the
covered components this contract lists). What the contract fixes is the
profile: the label `diagnos`, the exact component list for that request,
the parameter order, `alg="ed25519"`, the base64 framing, and that no
`Authorization` header is sent.

🇧🇷 A credencial de conta de serviço do contrato e os matchers de header RFC 9421 que toda interação leva.

A credencial é derivada de rótulos fixos (`fixed_bytes`), nunca guardada: a
mesma rodada produz a mesma identidade, e nenhuma chave — real ou falsa — é
escrita neste repositório. Os headers são travados pela *forma*: `created` e
`nonce` mudam a cada requisição por desenho, então a verificação do provider
no cofre reassina cada requisição repetida com uma chave que ele mesmo semeou
(o filtro de requisição dele troca `Signature-Input`/`Signature`, mantendo os
componentes cobertos que este contrato lista). O que o contrato fixa é o
perfil: o rótulo `diagnos`, a lista exata de componentes daquela requisição,
a ordem dos parâmetros, `alg="ed25519"`, o enquadramento base64, e que nenhum
header `Authorization` é enviado.
"""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Final, cast

from pact import match

from diagnos.crypto.secure import SecretBox
from diagnos.transport.credential import ServiceAccountCredential
from diagnos.transport.message_signature import covered_components, signature_params

from _crypto import b64url, fixed_bytes

WORKSPACE: Final = "ws-contract"
CREATED: Final = 1_780_000_000
IDENTITY: Final = f"svc_{fixed_bytes('credential/key-id', 16).hex()}@{WORKSPACE}.diagnos.health"
_IDENTITY_RE: Final = r"svc_[0-9a-f]{32}@[A-Za-z0-9_-]+\.diagnos\.health"


def credential() -> ServiceAccountCredential:
    """🇺🇸 The contract's credential — a fresh box per call, since a test may wipe it.

    🇧🇷 A credencial do contrato — caixa nova por chamada, já que um teste pode apagá-la.
    """
    return ServiceAccountCredential(IDENTITY, SecretBox.from_bytes(bytearray(fixed_bytes("credential/seed"))))


def public_key() -> str:
    """🇺🇸 What the vault's state handler registers for `IDENTITY`. 🇧🇷 O que o state handler registra para `IDENTITY`."""
    return credential().public_key


def identity_headers(*, query: bool = False, body: bool = False) -> dict[str, str]:
    """🇺🇸 `Signature-Input`/`Signature` (and `Content-Digest` with a body) for a request of this shape.

    🇧🇷 `Signature-Input`/`Signature` (e `Content-Digest` com corpo) para uma requisição desta forma.
    """
    components = covered_components(has_query=query, has_body=body)
    nonce = b64url(fixed_bytes("credential/nonce", 16))
    example = signature_params(components, created=CREATED, keyid=IDENTITY, nonce=nonce)
    inner = re.escape(" ".join(f'"{component}"' for component in components))
    pattern = (
        rf'^diagnos=\({inner}\);created=[0-9]{{10}};keyid="{_IDENTITY_RE}";nonce="[A-Za-z0-9_-]{{22}}";alg="ed25519"$'
    )
    signature = base64.b64encode(fixed_bytes("credential/signature", 64)).decode()
    headers: dict[str, object] = {
        "Signature-Input": match.regex(f"diagnos={example}", regex=pattern),
        "Signature": match.regex(f"diagnos=:{signature}:", regex=r"^diagnos=:[A-Za-z0-9+/]{86}==:$"),
    }
    if body:
        digest = base64.b64encode(hashlib.sha256(b"{}").digest()).decode()
        headers["Content-Digest"] = match.regex(f"sha-256=:{digest}:", regex=r"^sha-256=:[A-Za-z0-9+/]{43}=:$")
    return cast(dict[str, str], headers)
