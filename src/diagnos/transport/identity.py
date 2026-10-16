"""🇺🇸 `RequestIdentity`: what the transport needs from "who is calling", whichever token that is.

Two shapes satisfy it: `DiagnosToken` (`dgn_sk1_…`, Ed25519 + ML-DSA-65 over
RFC 9421 — the current one) and `ServiceAccountToken` (the deprecated
`apikey-` bearer, accepted until 2027-04-15). The transport asks for headers
once per attempt, so a retry always carries a fresh signature and nonce.

🇧🇷 `RequestIdentity`: o que o transporte precisa de "quem está chamando", seja qual for o token.

Duas formas a satisfazem: `DiagnosToken` (`dgn_sk1_…`, Ed25519 + ML-DSA-65
sobre RFC 9421 — o atual) e `ServiceAccountToken` (o bearer `apikey-`
obsoleto, aceito até 2027-04-15). O transporte pede os headers uma vez por
tentativa, então uma retentativa sempre leva assinatura e nonce novos.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import httpx


class RequestIdentity(Protocol):
    """🇺🇸 The token-agnostic face the transport and the session layer use.

    🇧🇷 A face agnóstica de token que o transporte e a camada de sessão usam.
    """

    @property
    def workspace_id(self) -> str:
        """🇺🇸 The workspace every path is scoped to. 🇧🇷 O workspace a que todo path se restringe."""
        ...

    @property
    def key_id(self) -> str:
        """🇺🇸 The key an admin rotates or revokes. 🇧🇷 A chave que um admin gira ou revoga."""
        ...

    @property
    def signs_requests(self) -> bool:
        """🇺🇸 Whether headers depend on the clock (`created`), so it must be synced first.

        🇧🇷 Se os headers dependem do relógio (`created`), e ele precisa ser sincronizado antes.
        """
        ...

    def request_headers(self, method: str, url: httpx.URL, body: bytes, created: int) -> dict[str, str]:
        """🇺🇸 The identity headers for one attempt. 🇧🇷 Os headers de identidade de uma tentativa."""
        ...
