r"""🇺🇸 HTTP Message Signatures (RFC 9421), the minimal profile the vault verifies — the credential's proof of identity.

Every external request carries `Signature-Input`, `Signature` and, when it
has a body, `Content-Digest` (RFC 9530). The signature base is built exactly
as RFC 9421 §2.5 says: one `"component": value` line per covered component,
in the order `Signature-Input` lists them, then `"@signature-params"` — the
`Signature-Input` value without its label — joined by `\n`, no trailing
newline. The vault rebuilds the same string from the raw request, so every
choice below is fixed by the service account credential spec (§3), never
"what seems reasonable":

- covered components: `@method`, `@path`, `@query` only if there is a query
  string, `content-digest` only if there is a body;
- `@path` and `@query` are the bytes on the wire (`httpx.URL.raw_path`),
  still percent-encoded and in the order sent — never decoded or sorted;
- parameters in this order: `created`, `keyid` (the full identity),
  `nonce` (16 random bytes, base64url), `alg="ed25519"`.

🇧🇷 HTTP Message Signatures (RFC 9421), o perfil mínimo que o cofre verifica — a prova de identidade da credencial.

Toda requisição externa leva `Signature-Input`, `Signature` e, quando tem
corpo, `Content-Digest` (RFC 9530). A signature base é montada exatamente como
diz a RFC 9421 §2.5: uma linha `"componente": valor` por componente coberto,
na ordem em que o `Signature-Input` os lista, depois `"@signature-params"` — o
valor do `Signature-Input` sem o rótulo — unidas por `\n`, sem quebra de linha
final. O cofre remonta a mesma string a partir da requisição crua, então toda
escolha abaixo é fixada pela spec da credencial de conta de serviço (§3),
nunca "o que parece razoável":

- componentes cobertos: `@method`, `@path`, `@query` só se houver query
  string, `content-digest` só se houver corpo;
- `@path` e `@query` são os bytes do fio (`httpx.URL.raw_path`), ainda
  percent-encoded e na ordem enviada — nunca decodificados nem ordenados;
- parâmetros nesta ordem: `created`, `keyid` (a identidade completa),
  `nonce` (16 bytes aleatórios, base64url), `alg="ed25519"`.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from typing import Final

import httpx

SIGNATURE_LABEL: Final = "diagnos"
ALGORITHM: Final = "ed25519"


def _b64(data: bytes) -> str:
    """🇺🇸 Standard base64 with padding — what RFC 8941 byte sequences use. 🇧🇷 base64 padrão com padding (RFC 8941)."""
    return base64.b64encode(data).decode("ascii")


def content_digest(body: bytes) -> str:
    """🇺🇸 The `Content-Digest` value (RFC 9530): `sha-256=:<base64>:`. 🇧🇷 O valor de `Content-Digest` (RFC 9530)."""
    return f"sha-256=:{_b64(hashlib.sha256(body).digest())}:"


def covered_components(*, has_query: bool, has_body: bool) -> tuple[str, ...]:
    """🇺🇸 `@method`, `@path`, then `@query`/`content-digest` only when present.

    🇧🇷 `@method`, `@path`, depois `@query`/`content-digest` só quando presentes.
    """
    components = ["@method", "@path"]
    if has_query:
        components.append("@query")
    if has_body:
        components.append("content-digest")
    return tuple(components)


def signature_params(components: tuple[str, ...], *, created: int, keyid: str, nonce: str) -> str:
    """🇺🇸 The inner list plus parameters — `Signature-Input` without its label, and the last line of the base.

    🇧🇷 A lista interna mais os parâmetros — o `Signature-Input` sem rótulo, e a última linha da base.
    """
    inner = " ".join(f'"{component}"' for component in components)
    return f'({inner});created={created};keyid="{keyid}";nonce="{nonce}";alg="{ALGORITHM}"'


def signature_base(*, method: str, path: str, query: str, digest: str | None, params: str) -> str:
    """🇺🇸 The exact string Ed25519 signs (RFC 9421 §2.5); `query` without its `?`, empty when there is none.

    🇧🇷 A string exata que o Ed25519 assina (RFC 9421 §2.5); `query` sem o `?`, vazia quando não há.
    """
    lines = [f'"@method": {method.upper()}', f'"@path": {path}']
    if query:
        lines.append(f'"@query": ?{query}')
    if digest is not None:
        lines.append(f'"content-digest": {digest}')
    lines.append(f'"@signature-params": {params}')
    return "\n".join(lines)


def identity_headers(
    sign: Callable[[bytes], bytes],
    *,
    keyid: str,
    method: str,
    url: httpx.URL,
    body: bytes,
    created: int,
    nonce: str,
) -> dict[str, str]:
    """🇺🇸 `Signature-Input`, `Signature` and (with a body) `Content-Digest` for one request.

    `sign` is the credential's Ed25519 signer: the seed never comes here.
    An empty body is "no body" — no digest, no `content-digest` component —
    which is how the vault reads a `GET` or a body-less `POST`.

    🇧🇷 `Signature-Input`, `Signature` e (com corpo) `Content-Digest` de uma requisição.

    `sign` é o assinador Ed25519 da credencial: a semente nunca chega aqui.
    Corpo vazio é "sem corpo" — sem digest, sem componente
    `content-digest` — que é como o cofre lê um `GET` ou um `POST` sem corpo.
    """
    path, _, query = url.raw_path.decode("ascii").partition("?")
    digest = content_digest(body) if body else None
    components = covered_components(has_query=bool(query), has_body=digest is not None)
    params = signature_params(components, created=created, keyid=keyid, nonce=nonce)
    base = signature_base(method=method, path=path, query=query, digest=digest, params=params)
    headers = {
        "Signature-Input": f"{SIGNATURE_LABEL}={params}",
        "Signature": f"{SIGNATURE_LABEL}=:{_b64(sign(base.encode('utf-8')))}:",
    }
    if digest is not None:
        headers["Content-Digest"] = digest
    return headers
