"""🇺🇸 Drive file bodies: libsodium `crypto_secretstream_xchacha20poly1305`, length-framed (PROTOCOL §9).

The AEAD primitive demands byte-identical chunks between `push` and `pull` —
each chunk carries its own authentication tag, so feeding it a
differently-sized slice fails by design. But bytes arrive at arbitrary
boundaries dictated by the network (an HTTP body, a multipart part), never
aligned with the boundaries used when encrypting. The `[len uint32 BE][cipher
chunk]` framing is what lets the reading side reassemble the exact original
chunks before calling `pull`, no matter how the bytes were split in transit.
The vault's web client uses the same framing and the same push/pull
wrapper, one layer down; `tests/vectors/secretstream.json` pins both. The stream state (the
ratcheting key) lives inside the enclave; only content crosses into Python.

🇧🇷 Corpo dos arquivos do drive: libsodium `crypto_secretstream_xchacha20poly1305`, framed por tamanho (PROTOCOL §9).

A primitiva AEAD exige chunks idênticos byte a byte entre `push` e `pull` —
cada chunk carrega sua própria tag de autenticação, então alimentá-la com um
pedaço de tamanho diferente falha por desenho. Mas os bytes chegam em
fronteiras arbitrárias ditadas pela rede (um corpo HTTP, uma parte de
multipart), nunca alinhadas com as fronteiras usadas ao cifrar. O framing
`[len uint32 BE][cipher chunk]` é o que permite ao lado da leitura remontar
os chunks originais exatos antes de chamar `pull`, não importa como os bytes
chegaram fragmentados no transporte. O estado do stream (a chave que
rotaciona) vive dentro do enclave; só conteúdo atravessa para o Python.
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

# 🇺🇸 `BinaryIO` covers a file handle (`.read(n)`); `Iterable[bytes]` covers
#    anything already chunked (a list of parts, a generator over a request
#    body). Both are normalized to fixed-size pieces by `_iter_fixed_chunks`.
# 🇧🇷 `BinaryIO` cobre um handle de arquivo (`.read(n)`); `Iterable[bytes]`
#    cobre qualquer coisa já em pedaços (uma lista de partes, um gerador
#    sobre um corpo de requisição). As duas são normalizadas em pedaços de
#    tamanho fixo por `_iter_fixed_chunks`.
StreamSource = Iterable[bytes] | BinaryIO


def encrypted_size(plaintext_size: int, chunk_size: int = CHUNK_SIZE) -> int:
    """🇺🇸 The exact encrypted+framed size, computed *before* uploading — the web app's `encryptedLength`.

    One frame per full chunk plus one final frame for the remainder (empty
    when the plaintext is an exact multiple of the chunk, and for an empty
    file): `24 + (n // chunk + 1) × (4 + 17) + n`. The vault locks a single
    `PUT` to this number and charges the workspace by it, so it must match
    what `encrypt_stream` produces byte for byte.

    🇧🇷 O tamanho exato cifrado e framed, calculado *antes* de subir — o `encryptedLength` do app web.

    Um frame por chunk cheio mais um frame final com o resto (vazio quando o
    texto claro é múltiplo exato do chunk, e para arquivo vazio):
    `24 + (n // chunk + 1) × (4 + 17) + n`. O cofre trava um `PUT` único
    neste número e cobra o workspace por ele, então precisa bater byte a
    byte com o que `encrypt_stream` produz.
    """
    if plaintext_size < 0:
        raise CryptoError("encrypted_size: plaintext_size não pode ser negativo")
    frames = plaintext_size // chunk_size + 1
    return HEADER_BYTES + frames * (_LENGTH_PREFIX_BYTES + ABYTES) + plaintext_size


def _iter_fixed_chunks(source: StreamSource, chunk_size: int) -> Iterator[bytes]:
    """🇺🇸 Normalizes either input shape into pieces of exactly `chunk_size` bytes (last one may be shorter).

    🇧🇷 Normaliza qualquer um dos formatos de entrada em pedaços de exatamente
    `chunk_size` bytes (o último pode ser menor).
    """
    if hasattr(source, "read"):
        reader: BinaryIO = source  # type: ignore[assignment]
        while True:
            piece = reader.read(chunk_size)
            if not piece:
                return
            # 🇺🇸 `.read(n)` on a file-like object may short-read even with
            #    more data ahead — top it up before yielding.
            # 🇧🇷 `.read(n)` num objeto tipo-arquivo pode ler menos que `n`
            #    mesmo havendo mais dado adiante — completa antes de entregar.
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
    """🇺🇸 `[len uint32 BE][cipher chunk]`, matching `framing.ts#encodeFrame`.

    🇧🇷 `[len uint32 BE][chunk cifrado]`, espelhando `framing.ts#encodeFrame`.
    """
    return len(cipher_chunk).to_bytes(_LENGTH_PREFIX_BYTES, "big") + cipher_chunk


def encrypt_stream(key: SecretLike, source: StreamSource, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """🇺🇸 Yields the 24-byte header, then one framed ciphertext chunk at a time, framed like the web app.

    Every full chunk is pushed as a regular message; the remainder — empty
    when the plaintext is an exact multiple of `chunk_size`, and for an empty
    source — always closes the stream as its own `TAG_FINAL` frame. That tag
    is what lets the reader (`decrypt_stream`) tell a stream cut short by a
    failed upload from one that legitimately ended.

    🇧🇷 Entrega o header de 24 bytes, depois um chunk cifrado framed por vez, enquadrado como no app web.

    Todo chunk cheio vai como mensagem comum; o resto — vazio quando o texto
    claro é múltiplo exato de `chunk_size`, e para fonte vazia — sempre fecha
    o stream como o próprio frame `TAG_FINAL`. Essa tag é o que permite ao
    leitor (`decrypt_stream`) distinguir um stream cortado por um upload que
    falhou de um que terminou de verdade.
    """
    push = _secure.SecretStreamPush(as_secret(key))
    yield push.header

    tail = b""
    for chunk in _iter_fixed_chunks(source, chunk_size):
        if len(chunk) == chunk_size:
            yield _encode_frame(push.push(chunk))
        else:
            # 🇺🇸 Only the last piece can be short. 🇧🇷 Só o último pedaço pode ser curto.
            tail = chunk
    yield _encode_frame(push.push(tail, final=True))


def decrypt_stream(key: SecretLike, source: Iterable[bytes]) -> Iterator[bytes]:
    """🇺🇸 Reassembles frames from arbitrary chunk boundaries and yields plaintext.

    Raises `CryptoError` on a tampered or out-of-order chunk (the AEAD
    itself detects it), on any byte arriving after `TAG_FINAL`, and on a
    stream that ends without ever producing `TAG_FINAL` — the three ways a
    partial or manipulated upload could otherwise look like a valid file.

    🇧🇷 Remonta frames a partir de fronteiras de chunk arbitrárias e entrega texto claro.

    Lança `CryptoError` em chunk adulterado ou fora de ordem (o próprio AEAD
    detecta), em qualquer byte depois do `TAG_FINAL`, e num stream que
    termina sem nunca produzir `TAG_FINAL` — as três formas de um upload
    parcial ou manipulado poder, de outro jeito, parecer um arquivo válido.
    """
    iterator = iter(source)
    buffer = bytearray()

    def fill(target: int) -> bool:
        """🇺🇸 Reads until `buffer` has ≥ `target` bytes; `False` if the source ran out first.

        🇧🇷 Lê até `buffer` ter ≥ `target` bytes; `False` se a fonte acabou antes.
        """
        while len(buffer) < target:
            try:
                buffer.extend(next(iterator))
            except StopIteration:
                return False
        return True

    if not fill(HEADER_BYTES):
        raise CryptoError("decrypt_stream: stream truncado (header ausente)")
    header = bytes(buffer[:HEADER_BYTES])
    del buffer[:HEADER_BYTES]

    try:
        pull = _secure.SecretStreamPull(as_secret(key), header)
    except SecureError as exc:
        raise CryptoError("decrypt_stream: header inválido") from exc

    finished = False
    while fill(_LENGTH_PREFIX_BYTES):
        if finished:
            raise CryptoError("decrypt_stream: dado após TAG_FINAL")
        length = int.from_bytes(bytes(buffer[:_LENGTH_PREFIX_BYTES]), "big")
        del buffer[:_LENGTH_PREFIX_BYTES]

        if not fill(length):
            raise CryptoError("decrypt_stream: stream truncado (chunk incompleto)")
        cipher_chunk = bytes(buffer[:length])
        del buffer[:length]

        try:
            message, finished = pull.pull(cipher_chunk)
        except SecureError as exc:
            raise CryptoError("decrypt_stream: chunk fora de ordem ou adulterado") from exc
        yield message

    if not finished:
        raise CryptoError("decrypt_stream: stream truncado (TAG_FINAL ausente)")


def encrypt_bytes(key: SecretLike, data: bytes) -> bytes:
    """🇺🇸 `encrypt_stream` for an in-memory blob, fully materialized.

    🇧🇷 `encrypt_stream` para um blob em memória, já materializado.
    """
    return b"".join(encrypt_stream(key, [data]))


def decrypt_bytes(key: SecretLike, data: bytes) -> bytes:
    """🇺🇸 `decrypt_stream` for an in-memory blob, fully materialized.

    🇧🇷 `decrypt_stream` para um blob em memória, já materializado.
    """
    return b"".join(decrypt_stream(key, [data]))
