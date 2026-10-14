"""`DIAGNOS_API_TOKEN` parsing: the SDK's own identity, not the vault's.

The token is `apikey-<JWT EdDSA>`. The SDK never verifies the signature, and
has no business doing so, because the vault is the only party that can (it
holds the workspace's signing key, and revocation is server-side). All the
SDK needs from the JWT is `workspace_id`, to build the URLs every resource
call targets, so this module just decodes the payload as opaque JSON and
checks that the claims it depends on are there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from diagnos.crypto.encoding import b64url_decode
from diagnos.errors import ConfigError

_PREFIX = "apikey-"
_REQUIRED_CLAIMS = ("sub", "account_id", "workspace_id", "name")


def redact_api_token(token: str) -> str:
    """Redact `apikey-<jwt>` to `apikey-…<last 4 chars>` for logs and `repr`.

    That is enough to tell two tokens apart (or confirm one did not change)
    without ever printing bytes that grant API access.

    Args:
        token: The raw token.

    Returns:
        The redacted form.
    """
    tail = token[-4:] if len(token) >= 4 else token
    return f"{_PREFIX}…{tail}"


@dataclass(frozen=True)
class ServiceAccountToken:
    """The decoded shape of `DIAGNOS_API_TOKEN`, whose signature is deliberately not checked.

    Attributes:
        raw: The full token, `apikey-<jwt>`.
        key_id: The id of the token's key pair (the `sub` claim), which is what an admin rotates or revokes.
        account_id: The service account's owning account.
        workspace_id: The workspace the token belongs to.
        name: The service account's human-readable name.
    """

    raw: str
    key_id: str
    account_id: str
    workspace_id: str
    name: str

    @classmethod
    def parse(cls, raw: str) -> ServiceAccountToken:
        """Decode `apikey-<jwt>` into its claims, without checking the signature.

        A missing prefix or claim is a configuration mistake the caller can
        fix (wrong env var, copy-pasted the wrong secret), so it raises
        `ConfigError`, not `CryptoError`, which is reserved for envelopes that
        should have opened and did not.

        Args:
            raw: The raw `DIAGNOS_API_TOKEN` value.

        Returns:
            The parsed token.

        Raises:
            ConfigError: If the prefix, the JWT shape or a required claim is wrong.
        """
        if not raw.startswith(_PREFIX):
            raise ConfigError(
                "DIAGNOS_API_TOKEN must start with 'apikey-'; check you copied the "
                "full service account token from the vault."
            )
        jwt = raw[len(_PREFIX) :]
        segments = jwt.split(".")
        if len(segments) != 3:
            raise ConfigError(
                "DIAGNOS_API_TOKEN does not carry a JWT with three segments "
                "(header.payload.signature); the token looks truncated or corrupted."
            )
        try:
            payload = json.loads(b64url_decode(segments[1]))
        except Exception as exc:
            raise ConfigError("DIAGNOS_API_TOKEN's JWT payload is not valid base64url JSON.") from exc
        if not isinstance(payload, dict):
            raise ConfigError("DIAGNOS_API_TOKEN's JWT payload must be a JSON object.")
        missing = [claim for claim in _REQUIRED_CLAIMS if claim not in payload]
        if missing:
            raise ConfigError(
                f"DIAGNOS_API_TOKEN's JWT is missing claim(s) {missing}; it was not "
                "issued the way the vault issues service account tokens."
            )
        return cls(
            raw=raw,
            key_id=str(payload["sub"]),
            account_id=str(payload["account_id"]),
            workspace_id=str(payload["workspace_id"]),
            name=str(payload["name"]),
        )

    def authorization_header(self) -> dict[str, str]:
        """Return the one header every request needs, signed or not: `Authorization: Bearer <token>`."""
        return {"Authorization": f"Bearer {self.raw}"}

    def __repr__(self) -> str:
        """Render the token redacted, because this repr ends up in logs and tracebacks."""
        return (
            f"ServiceAccountToken(key_id={self.key_id!r}, account_id={self.account_id!r}, "
            f"workspace_id={self.workspace_id!r}, name={self.name!r}, raw={redact_api_token(self.raw)!r})"
        )
