"""base64url without padding — the only text encoding of bytes in the protocol."""

from __future__ import annotations

import base64


def b64url_encode(data: bytes | bytearray) -> str:
    """Encode bytes as unpadded base64url (RFC 4648 §5).

    Args:
        data: The bytes to encode.

    Returns:
        The ASCII text, with the trailing `=` padding removed.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    """Decode base64url text, with or without trailing `=` padding.

    Args:
        text: The base64url text.

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If `text` is not valid base64url (including non-ASCII input).
    """
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
