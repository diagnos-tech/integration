"""Drive file bodies: libsodium `crypto_secretstream_xchacha20poly1305`, length-framed (PROTOCOL §9).

The AEAD primitive demands byte-identical chunks between `push` and `pull`:
each chunk carries its own authentication tag, so feeding it a
differently-sized slice fails by design. But bytes arrive at arbitrary
boundaries dictated by the network (an HTTP body, a multipart part), never
aligned with the boundaries used when encrypting. The `[len uint32 BE][cipher
chunk]` framing is what lets the reading side reassemble the exact original
chunks before calling `pull`, no matter how the bytes were split in transit.
The vault's web client uses the same framing and the same push/pull
wrapper, one layer down; `tests/vectors/secretstream.json` pins both. The
stream state (the ratcheting key) lives inside the enclave; only content
crosses into Python.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import BinaryIO

from diagnos import _secure
from diagnos.errors import CryptoError

from .secure import SecretLike, SecureError, as_secret

CHUNK_SIZE = 1024 * 1024
HEADER_BYTES = _secure.SECRETSTREAM_HEADER_BYTES
ABYTES = _secure.SECRETSTREAM_ABYTES

_LENGTH_PREFIX_BYTES = 4

# `BinaryIO` covers a file handle (`.read(n)`); `Iterable[bytes]` covers
# anything already chunked (a list of parts, a generator over a request
# body). Both are normalized to fixed-size pieces by `_iter_fixed_chunks`.
StreamSource = Iterable[bytes] | BinaryIO


def encrypted_size(plaintext_size: int, chunk_size: int = CHUNK_SIZE) -> int:
    """Compute the exact encrypted and framed size *before* uploading, as the web app's `encryptedLength` does.

    There is one frame per full chunk plus one final frame for the remainder
    (empty when the plaintext is an exact multiple of the chunk, and for an
    empty file): `24 + (n // chunk + 1) × (4 + 17) + n`. The vault locks a
    single `PUT` to this number and charges the workspace by it, so it must
    match what `encrypt_stream` produces byte for byte.

    Args:
        plaintext_size: The plaintext length in bytes.
        chunk_size: The chunk size `encrypt_stream` will use.

    Returns:
        The length in bytes of the header plus all frames.

    Raises:
        CryptoError: If `plaintext_size` is negative.
    """
    if plaintext_size < 0:
        raise CryptoError("encrypted_size: plaintext_size must not be negative")
    frames = plaintext_size // chunk_size + 1
    return HEADER_BYTES + frames * (_LENGTH_PREFIX_BYTES + ABYTES) + plaintext_size


def _iter_fixed_chunks(source: StreamSource, chunk_size: int) -> Iterator[bytes]:
    """Normalize either input shape into pieces of exactly `chunk_size` bytes (the last one may be shorter)."""
    if hasattr(source, "read"):
        reader: BinaryIO = source  # type: ignore[assignment]
        while True:
            piece = reader.read(chunk_size)
            if not piece:
                return
            # `.read(n)` on a file-like object may short-read even with
            # more data ahead, so top it up before yielding.
            while len(piece) < chunk_size:
                more = reader.read(chunk_size - len(piece))
                if not more:
                    break
                piece += more
            yield piece
    else:
        buffer = bytearray()
        for piece in source:
            buffer.extend(piece)
            while len(buffer) >= chunk_size:
                yield bytes(buffer[:chunk_size])
                del buffer[:chunk_size]
        if buffer:
            yield bytes(buffer)


def _encode_frame(cipher_chunk: bytes) -> bytes:
    """Frame a cipher chunk as `[len uint32 BE][cipher chunk]`, matching `framing.ts#encodeFrame`."""
    return len(cipher_chunk).to_bytes(_LENGTH_PREFIX_BYTES, "big") + cipher_chunk


def encrypt_stream(key: SecretLike, source: StreamSource, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Yield the 24-byte header, then one framed ciphertext chunk at a time, framed like the web app.

    Every full chunk is pushed as a regular message. The remainder (empty
    when the plaintext is an exact multiple of `chunk_size`, and for an empty
    source) always closes the stream as its own `TAG_FINAL` frame. That tag
    is what lets the reader (`decrypt_stream`) tell a stream cut short by a
    failed upload from one that legitimately ended.

    Args:
        key: The 32-byte stream key.
        source: A binary file object, or any iterable of byte chunks of arbitrary size.
        chunk_size: The plaintext size of each full chunk.

    Yields:
        The header first, then one `[len uint32 BE][cipher chunk]` frame per chunk.
    """
    push = _secure.SecretStreamPush(as_secret(key))
    yield push.header

    tail = b""
    for chunk in _iter_fixed_chunks(source, chunk_size):
        if len(chunk) == chunk_size:
            yield _encode_frame(push.push(chunk))
        else:
            # Only the last piece can be short.
            tail = chunk
    yield _encode_frame(push.push(tail, final=True))


def decrypt_stream(key: SecretLike, source: Iterable[bytes]) -> Iterator[bytes]:
    """Reassemble frames from arbitrary chunk boundaries and yield plaintext.

    These are the three ways a partial or manipulated upload could otherwise
    look like a valid file, and each one raises `CryptoError`: a tampered or
    out-of-order chunk (the AEAD itself detects it), any byte arriving after
    `TAG_FINAL`, and a stream that ends without ever producing `TAG_FINAL`.

    Args:
        key: The 32-byte stream key.
        source: The framed stream, split into byte chunks at arbitrary boundaries.

    Yields:
        The plaintext of each frame, in order.

    Raises:
        CryptoError: If the stream is truncated, tampered with, out of order, or has trailing data.
    """
    iterator = iter(source)
    buffer = bytearray()

    def fill(target: int) -> bool:
        """Read until `buffer` has at least `target` bytes; return `False` if the source ran out first."""
        while len(buffer) < target:
            try:
                buffer.extend(next(iterator))
            except StopIteration:
                return False
        return True

    if not fill(HEADER_BYTES):
        raise CryptoError("decrypt_stream: truncated stream (header missing)")
    header = bytes(buffer[:HEADER_BYTES])
    del buffer[:HEADER_BYTES]

    try:
        pull = _secure.SecretStreamPull(as_secret(key), header)
    except SecureError as exc:
        raise CryptoError("decrypt_stream: invalid header") from exc

    finished = False
    while fill(_LENGTH_PREFIX_BYTES):
        if finished:
            raise CryptoError("decrypt_stream: data after TAG_FINAL")
        length = int.from_bytes(bytes(buffer[:_LENGTH_PREFIX_BYTES]), "big")
        del buffer[:_LENGTH_PREFIX_BYTES]

        if not fill(length):
            raise CryptoError("decrypt_stream: truncated stream (incomplete chunk)")
        cipher_chunk = bytes(buffer[:length])
        del buffer[:length]

        try:
            message, finished = pull.pull(cipher_chunk)
        except SecureError as exc:
            raise CryptoError("decrypt_stream: chunk out of order or tampered with") from exc
        yield message

    if not finished:
        raise CryptoError("decrypt_stream: truncated stream (TAG_FINAL missing)")


def encrypt_bytes(key: SecretLike, data: bytes) -> bytes:
    """Run `encrypt_stream` over an in-memory blob and return the whole framed ciphertext.

    Args:
        key: The 32-byte stream key.
        data: The plaintext.

    Returns:
        The header followed by every frame, concatenated.
    """
    return b"".join(encrypt_stream(key, [data]))


def decrypt_bytes(key: SecretLike, data: bytes) -> bytes:
    """Run `decrypt_stream` over an in-memory blob and return the whole plaintext.

    Args:
        key: The 32-byte stream key.
        data: The framed ciphertext produced by `encrypt_bytes`.

    Returns:
        The plaintext.

    Raises:
        CryptoError: If the stream is truncated, tampered with, out of order, or has trailing data.
    """
    return b"".join(decrypt_stream(key, [data]))
