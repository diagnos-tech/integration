"""🇺🇸 The vocabulary every interaction is written in: the fixed identity, header matchers, the envelope.

Two rules decide what goes into a matcher and what stays literal, and they
are the whole point of a consumer-driven contract:

1. Only what the SDK *reads* goes into a response. The vault may send more
   (Pact allows extra keys in a response body); the contract pins exactly
   what the SDK would break without — nothing it merely tolerates.
2. A value is literal when the SDK branches on it (`"status": "approved"`,
   `"mode": "single"`, `"success": true`) and a matcher when only its shape
   matters (ids, timestamps, ciphertext). A renamed enum is a broken SDK;
   a different id is not.

Everything the provider must produce in its own terms — the workspace id,
an enrollment id — travels as a provider-state parameter and a
`ProviderState` generator, so the vault's verification can substitute its
real values instead of guessing ours.

🇧🇷 O vocabulário em que toda interação é escrita: a identidade fixa, matchers de header, o envelope.

Duas regras decidem o que vira matcher e o que fica literal, e são o ponto
inteiro de um contrato guiado pelo consumidor:

1. Só o que o SDK *lê* entra numa resposta. O cofre pode mandar mais (o Pact
   aceita chave a mais num corpo de resposta); o contrato trava exatamente o
   que quebraria o SDK — nada que ele só tolera.
2. Um valor é literal quando o SDK decide com base nele
   (`"status": "approved"`, `"mode": "single"`, `"success": true`) e matcher
   quando só a forma importa (ids, timestamps, ciphertext). Um enum renomeado
   é um SDK quebrado; um id diferente não.

Tudo que o provider precisa produzir nos próprios termos — o id do
workspace, um id de enrollment — viaja como parâmetro de provider state e
gerador `ProviderState`, para a verificação do cofre substituir os valores
reais dela em vez de adivinhar os nossos.
"""

from __future__ import annotations

import json
from typing import Any, cast

from diagnos.crypto.secure import SecretBox
from diagnos.session.keyring import SessionKeys
from diagnos.transport.token import ServiceAccountToken
from pact import Pact, generate, match
from pact.match.matcher import GenericMatcher

from _crypto import b64url, fixed_bytes, random_seed

CONSUMER = "diagnos-sdk"
PROVIDER = "diagnos-vault"

WORKSPACE_ID = "ws-contract"
ACCOUNT_ID = "acc-contract"
KEY_ID = "key-contract"
SESSION_ID = "sess-contract"
SIGN_KEY = fixed_bytes("session/sign-key")
ENC_KEY = fixed_bytes("session/enc-key")
SERVER_TIME_MS = 1_780_000_000_000

B64URL = r"^[A-Za-z0-9_-]+$"
EXTERNAL_PREFIX = "/api/external/v1"


def _service_account_jwt() -> str:
    """🇺🇸 An `apikey-<jwt>` the SDK can parse; the signature is never checked on this side (`docs/PROTOCOL.md §1`).

    🇧🇷 Um `apikey-<jwt>` que o SDK consegue ler; a assinatura nunca é conferida deste lado (`docs/PROTOCOL.md §1`).
    """
    header = b64url(json.dumps({"alg": "EdDSA", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {
        "sub": KEY_ID,
        "account_id": ACCOUNT_ID,
        "workspace_id": WORKSPACE_ID,
        "name": f"contract@{WORKSPACE_ID}.diagnos.health",
    }
    payload = b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    return f"apikey-{header}.{payload}.{b64url(fixed_bytes('token/signature', 64))}"


API_TOKEN = _service_account_jwt()
TOKEN = ServiceAccountToken.parse(API_TOKEN)


def session_keys() -> SessionKeys:
    """🇺🇸 The session every signed interaction runs under — fresh boxes per call, since the SDK may wipe them.

    🇧🇷 A sessão sob a qual toda interação assinada roda — caixas novas por chamada, já que o SDK pode apagá-las.
    """
    return SessionKeys(
        session_id=SESSION_ID,
        sign_key=SecretBox.from_bytes(bytearray(SIGN_KEY)),
        enc_key=SecretBox.from_bytes(bytearray(ENC_KEY)),
        expires_at=9_999_999_999,
    )


# 🇺🇸 `HttpInteraction.with_headers` is typed `dict[str, str]` but, at runtime, hands each value to
#    `with_header`, which takes matchers too — `Headers` names that and `_headers` is the one cast.
# 🇧🇷 `HttpInteraction.with_headers` é tipado `dict[str, str]` mas, em runtime, repassa cada valor a
#    `with_header`, que aceita matchers — `Headers` dá nome a isso e `_headers` é o único cast.
Headers = dict[str, str]


def _headers(matchers: dict[str, object]) -> Headers:
    """🇺🇸 See `Headers`. 🇧🇷 Ver `Headers`."""
    return cast(Headers, matchers)


def workspace_state(name: str, **params: object) -> tuple[str, dict[str, object]]:
    """🇺🇸 A provider state that always carries `workspace_id`, so the vault can bind the path to its own workspace.

    🇧🇷 Um provider state que sempre leva `workspace_id`, para o cofre amarrar o path ao próprio workspace.
    """
    return name, {"workspace_id": WORKSPACE_ID, **params}


def path(example: str, *, pattern: str, expression: str | None = None) -> GenericMatcher[str]:
    """🇺🇸 A request path pinned by `pattern`, optionally rebuilt from provider-state values at verification time.

    `expression` uses `${name}` placeholders the vault's state handler fills
    in (Pact's `ProviderState` generator). The regex is what keeps the
    consumer side honest: a type matcher on a path would accept *any* path.

    🇧🇷 Um path travado por `pattern`, opcionalmente remontado com valores do provider state na verificação.

    `expression` usa marcadores `${nome}` que o state handler do cofre
    preenche (gerador `ProviderState` do Pact). A regex é o que mantém o lado
    do consumidor honesto: um matcher de tipo num path aceitaria *qualquer*
    path.
    """
    generator = generate.provider_state(expression) if expression is not None else None
    return GenericMatcher("regex", value=example, regex=pattern, generator=generator)


def bearer_header() -> Headers:
    """🇺🇸 `Authorization` on every request (`docs/PROTOCOL.md §1`) — its shape, not our fixed token.

    🇧🇷 `Authorization` em toda requisição (`docs/PROTOCOL.md §1`) — a forma, não o nosso token fixo.
    """
    return _headers(
        {
            "Authorization": match.regex(
                f"Bearer {API_TOKEN}", regex=r"^Bearer apikey-[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$"
            )
        }
    )


def signed_headers() -> Headers:
    """🇺🇸 Bearer plus the three `X-Signature-*` headers (`docs/PROTOCOL.md §3`).

    The vault's verification re-signs each replayed request with a session it
    seeded itself; what this contract pins is that the SDK always sends all
    four, in the right shape.

    🇧🇷 Bearer mais os três headers `X-Signature-*` (`docs/PROTOCOL.md §3`).

    A verificação do cofre reassina cada requisição repetida com uma sessão
    que ela mesma semeou; o que este contrato trava é que o SDK sempre manda
    os quatro, na forma certa.
    """
    return _headers(
        {
            **bearer_header(),
            "X-Signature-Timestamp": match.regex(str(SERVER_TIME_MS // 1000), regex=r"^[0-9]{10}$"),
            "X-Signature-Nonce": match.regex(b64url(fixed_bytes("nonce", 16)), regex=r"^[A-Za-z0-9_-]{22,}$"),
            "X-Signature-Hmac": match.regex("0" * 128, regex=r"^[0-9a-f]{128}$"),
        }
    )


def seed(*, label: str) -> dict[str, object]:
    """🇺🇸 The `random_seed` a signed response carries in its envelope (`docs/PROTOCOL.md §4`), openable by the SDK.

    🇧🇷 O `random_seed` que uma resposta assinada leva no envelope (`docs/PROTOCOL.md §4`), que o SDK consegue abrir.
    """
    return {"random_seed": encrypted(random_seed(ENC_KEY, SESSION_ID, label=label))}


def literal(value: object) -> GenericMatcher[object]:
    """🇺🇸 Exact value, even inside a `like`/`each_like` whose type rule would otherwise cascade down to it.

    🇧🇷 Valor exato, mesmo dentro de um `like`/`each_like` cuja regra de tipo senão desceria até ele.
    """
    return GenericMatcher("equality", value=value)


def ok(result: Any) -> dict[str, Any]:
    """🇺🇸 The success envelope, reduced to what `transport/envelope.py` reads: `success` and `result`.

    🇧🇷 O envelope de sucesso, reduzido ao que `transport/envelope.py` lê: `success` e `result`.
    """
    return {"success": True, "result": result}


def failure(code: str) -> dict[str, Any]:
    """🇺🇸 The failure envelope as the SDK reads it: `success: false` and the first error's `code` (literal).

    🇧🇷 O envelope de falha como o SDK o lê: `success: false` e o `code` do primeiro erro (literal).
    """
    return {"success": False, "errors": match.each_like({"code": literal(code), "message": match.str("…")})}


def encrypted(example: dict[str, str]) -> dict[str, object]:
    """🇺🇸 An `EncryptedPayload` (`docs/PROTOCOL.md §7`): three b64url strings, each pinned by shape only.

    🇧🇷 Um `EncryptedPayload` (`docs/PROTOCOL.md §7`): três strings b64url, cada uma travada só pela forma.
    """
    return {key: match.regex(value, regex=B64URL) for key, value in example.items()}


def declare_clock(pact: Pact) -> None:
    """🇺🇸 `GET /time` (`docs/PROTOCOL.md §2`): a raw `{"result"}`, no envelope, no auth.

    Every test that makes a signed call declares it too, because the SDK
    syncs its clock before the first signature of each transport.

    🇧🇷 `GET /time` (`docs/PROTOCOL.md §2`): um `{"result"}` cru, sem envelope, sem auth.

    Todo teste que faz uma chamada assinada também o declara, porque o SDK
    sincroniza o relógio antes da primeira assinatura de cada transporte.
    """
    (
        pact.upon_receiving("the vault's clock, to correct request signatures for skew")
        .with_request("GET", "/time")
        .will_respond_with(200)
        .with_body({"result": match.number(SERVER_TIME_MS)}, content_type="application/json")
    )
