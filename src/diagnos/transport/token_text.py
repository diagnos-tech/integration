"""🇺🇸 What the SDK says when a text is not a service account token — one fix per failure, never a byte of the text.

The codes come from the enclave's decoder (`crypto/token_keys.py`), the same
`reason`s the TypeScript reference uses. `encoding`, `length` and `checksum`
read the same to a person — the token was cut or pasted wrong — so they
share one message; the code stays on `TokenError.reason` for whoever needs
to tell them apart.

🇧🇷 O que o SDK diz quando um texto não é token de conta de serviço — uma correção por falha, nunca um byte do texto.

Os códigos vêm do decodificador do enclave (`crypto/token_keys.py`), os
mesmos `reason` da referência em TypeScript. `encoding`, `length` e
`checksum` dizem o mesmo a uma pessoa — o token foi cortado ou colado
errado — então dividem uma mensagem; o código fica em `TokenError.reason`
para quem precisar diferenciá-los.
"""

from __future__ import annotations

from typing import Final, NoReturn

from diagnos.errors import TokenError

PANEL: Final = "Settings → Service accounts · Configurações → Contas de serviço"
LEGACY_SUNSET: Final = "2027-04-15"

_TRUNCATED: Final = (
    "🇺🇸 the token is truncated or was pasted wrong (its checksum does not match). Copy it again in one piece: it is "
    "one line of about 100 characters starting with 'dgn_sk1_'. "
    "🇧🇷 o token está truncado ou foi colado errado (o checksum não confere). Copie de novo, inteiro: é uma linha "
    "de uns 100 caracteres que começa com 'dgn_sk1_'."
)
_MESSAGES: Final[dict[str, str]] = {
    "empty": "🇺🇸 is empty. 🇧🇷 está vazio.",
    "prefix": (
        f"🇺🇸 is not a diagnos service account token (those start with 'dgn_sk1_'). Create one under {PANEL} and "
        "copy the token it shows once. "
        f"🇧🇷 não é um token de conta de serviço do diagnos (eles começam com 'dgn_sk1_'). Crie um em {PANEL} e "
        "copie o token que aparece uma vez."
    ),
    "encoding": _TRUNCATED,
    "length": _TRUNCATED,
    "checksum": _TRUNCATED,
    "workspace": (
        "🇺🇸 the token's workspace id is malformed, so diagnos did not issue it; create a new one. "
        "🇧🇷 o id de workspace do token está malformado, então não foi o diagnos que o emitiu; crie um novo."
    ),
}
_LEGACY: Final = (
    f"🇺🇸 holds a legacy 'apikey-' token. Put it in DIAGNOS_API_TOKEN (deprecated, accepted until {LEGACY_SUNSET}) "
    "or create a service account token: https://dev.diagnos.health/migrating "
    f"🇧🇷 contém um token legado 'apikey-'. Coloque-o em DIAGNOS_API_TOKEN (obsoleto, aceito até {LEGACY_SUNSET}) "
    "ou crie um token de conta de serviço: https://dev.diagnos.health/migrating"
)


def refuse(source: str, reason: str, *, legacy: bool = False) -> NoReturn:
    """🇺🇸 Raise the `TokenError` for `reason`, naming where the text came from — never the text.

    🇧🇷 Lança o `TokenError` de `reason`, nomeando de onde o texto veio — nunca o texto.
    """
    message = _LEGACY if legacy else _MESSAGES.get(reason, _TRUNCATED)
    raise TokenError(f"{source} {message}", reason=reason, source=source)


def identity_of(key_id: str, workspace_id: str) -> str:
    """🇺🇸 `svc_<hex>@<workspace_id>.diagnos.health` — display only; the signed `keyid` is the key id alone.

    🇧🇷 `svc_<hex>@<workspace_id>.diagnos.health` — só exibição; o `keyid` assinado é só o id da chave.
    """
    return f"{key_id}@{workspace_id}.diagnos.health"
