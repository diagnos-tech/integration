"""🇺🇸 base64url without padding — the only text encoding of bytes in the protocol.

🇧🇷 base64url sem padding — a única codificação textual de bytes no protocolo.
"""

from __future__ import annotations

import base64


def b64url_encode(data: bytes | bytearray) -> str:
    """🇺🇸 RFC 4648 §5, padding stripped. 🇧🇷 RFC 4648 §5, sem padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    """🇺🇸 Accepts input with or without padding. 🇧🇷 Aceita com ou sem padding."""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
