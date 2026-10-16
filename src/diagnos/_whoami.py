"""🇺🇸 `Whoami`: what `Diagnos.whoami()` (and `diagnos whoami`) report once the vault accepted the token.

🇧🇷 `Whoami`: o que `Diagnos.whoami()` (e `diagnos whoami`) informam depois que o cofre aceitou o token.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Whoami:
    """🇺🇸 The token's identity and what the session opened with it was granted. Nothing in it is secret.

    🇧🇷 A identidade do token e o que a sessão aberta com ele recebeu. Nada aqui é segredo.
    """

    identity: str | None
    """🇺🇸 `svc_<hex>@<workspace_id>.diagnos.health`; `None` with the legacy token. 🇧🇷 `None` com o token legado."""
    key_id: str
    """🇺🇸 The key an admin rotates or revokes. 🇧🇷 A chave que um admin gira ou revoga."""
    workspace_id: str
    """🇺🇸 The workspace the token belongs to. 🇧🇷 O workspace a que o token pertence."""
    token_kind: Literal["hybrid", "legacy_apikey"]
    """🇺🇸 `hybrid` (`dgn_sk1_…`) or the deprecated `legacy_apikey`. 🇧🇷 `hybrid` ou o obsoleto `legacy_apikey`."""
    token_source: str
    """🇺🇸 Where the token was read from. 🇧🇷 De onde o token foi lido."""
    security_groups: list[str] = field(default_factory=list)
    """🇺🇸 The groups in the token's scope (their keys opened). 🇧🇷 Os grupos do escopo do token (chaves abertas)."""
    session_expires_at: int = 0
    """🇺🇸 When the session just opened expires, Unix seconds. 🇧🇷 Quando a sessão recém-aberta expira, em segundos."""
