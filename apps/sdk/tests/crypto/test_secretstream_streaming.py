"""🇺🇸 `crypto/secretstream.py`: chunk assembly from arbitrary reads, and every truncation/tamper shape of a stream.

`test_roundtrips.py` already proves the byte-for-byte round trip and a few
tamper/truncation modes; this file rounds out what `make cov` still flags:
the file-like reader's short-read top-up loop (`_iter_fixed_chunks`, both
branches — a read that already fills a chunk, and one that needs several
`.read()` calls to do it), a negative `plaintext_size`, a header the stream
never got to send at all, a wiped key handed to `decrypt_stream`, and a
stream that stops exactly on a frame boundary without ever producing
`TAG_FINAL` (the "upload cut off between two complete frames" shape,
distinct from `test_decrypt_stream_rejects_truncated_stream`'s
mid-frame cut).

🇧🇷 `crypto/secretstream.py`: montagem de chunk a partir de leituras
arbitrárias, e toda forma de truncamento/adulteração de um stream.

`test_roundtrips.py` já prova a ida-e-volta byte a byte e alguns modos de
adulteração/truncamento; este arquivo completa o que o `make cov` ainda
aponta: o laço de completar de leitura curta do leitor tipo-arquivo
(`_iter_fixed_chunks`, os dois ramos — uma leitura que já enche um chunk, e
uma que precisa de várias chamadas `.read()` para isso), um
`plaintext_size` negativo, um header que o stream nunca chegou a mandar,
uma chave apagada entregue a `decrypt_stream`, e um stream que para
exatamente numa fronteira de frame sem nunca produzir `TAG_FINAL` (a forma
"upload cortado entre dois frames completos", diferente do corte no meio de
um frame de `test_decrypt_stream_rejects_truncated_stream`).
"""

from __future__ import annotations

import secrets

import pytest
from diagnos.crypto.secretstream import (
    ABYTES,
    HEADER_BYTES,
    decrypt_stream,
    encrypt_stream,
    encrypted_size,
)
from diagnos.crypto.secure import SecretBox
from diagnos.errors import CryptoError

_SMALL_CHUNK = 32


class _ScriptedReader:
    """🇺🇸 A file-like object whose `.read(n)` returns exactly the pieces scripted, in order.

    Unlike `io.BytesIO`, this can return a *short* read (fewer bytes than
    asked for) even with more data still ahead — the exact situation
    `_iter_fixed_chunks`'s inner "top it up" loop exists for, which no
    `io.BytesIO`-backed test can reach.

    🇧🇷 Um objeto tipo-arquivo cujo `.read(n)` devolve exatamente os pedaços
    roteirizados, em ordem.

    Diferente de `io.BytesIO`, isto pode devolver uma leitura *curta* (menos
    bytes do que pedido) mesmo com mais dado pela frente — exatamente a
    situação para a qual o laço interno "completa" de `_iter_fixed_chunks`
    existe, que nenhum teste apoiado em `io.BytesIO` alcança.
    """

    def __init__(self, pieces: list[bytes]) -> None:
        """🇺🇸 `pieces`, exhausted one `.read()` call at a time, then empty forever.

        🇧🇷 `pieces`, consumidos um `.read()` por vez, depois vazio para sempre.
        """
        self._pieces = list(pieces)

    def read(self, _size: int) -> bytes:
        """🇺🇸 The next scripted piece, ignoring `_size` entirely — the caller tops up if it's short.

        🇧🇷 O próximo pedaço roteirizado, ignorando `_size` completamente — quem chama completa se for curto.
        """
        return self._pieces.pop(0) if self._pieces else b""


# -- _iter_fixed_chunks, via encrypt_stream ------------------------------------


def test_a_full_size_first_read_needs_no_top_up() -> None:
    """🇺🇸 When the first `.read()` already returns a whole chunk, no second `.read()` is needed for it.

    🇧🇷 Quando o primeiro `.read()` já devolve um chunk inteiro, nenhum segundo `.read()` é preciso para ele.
    """
    reader = _ScriptedReader([b"x" * _SMALL_CHUNK, b"tail"])
    key = secrets.token_bytes(32)

    frames = list(encrypt_stream(key, reader, chunk_size=_SMALL_CHUNK))  # type: ignore[arg-type]

    # 🇺🇸/🇧🇷 header + one full-chunk frame + the short tail's own final frame.
    assert len(frames) == 3
    assert len(frames[1]) - 4 == _SMALL_CHUNK + ABYTES


def test_a_short_first_read_is_topped_up_by_a_second_read() -> None:
    """🇺🇸 A short first `.read()` is completed by however many more `.read()` calls it takes.

    🇧🇷 Um primeiro `.read()` curto é completado por quantos `.read()` mais forem necessários.
    """
    reader = _ScriptedReader([b"a" * 10, b"b" * 20, b""])  # 🇺🇸/🇧🇷 10 + 20 == _SMALL_CHUNK
    key = secrets.token_bytes(32)

    frames = list(encrypt_stream(key, reader, chunk_size=_SMALL_CHUNK))  # type: ignore[arg-type]
    decrypted = b"".join(decrypt_stream(key, [b"".join(frames)]))

    assert decrypted == b"a" * 10 + b"b" * 20


# -- encrypted_size -------------------------------------------------------------


def test_encrypted_size_rejects_a_negative_plaintext_size() -> None:
    """🇺🇸 A negative size cannot be sealed; it is a caller mistake, not a `0`-byte file.

    🇧🇷 Um tamanho negativo não pode ser selado; é um engano de quem chama, não um arquivo de `0` bytes.
    """
    with pytest.raises(CryptoError):
        encrypted_size(-1)


# -- decrypt_stream: truncation, a wiped key, and a boundary-aligned cutoff ----


def test_decrypt_stream_rejects_a_stream_with_no_header_at_all() -> None:
    """🇺🇸 Fewer than `HEADER_BYTES` bytes total (an upload cut off before the header even landed) is `CryptoError`.

    🇧🇷 Menos que `HEADER_BYTES` bytes no total (upload cortado antes do header sequer chegar) é `CryptoError`.
    """
    key = secrets.token_bytes(32)
    with pytest.raises(CryptoError, match="header ausente"):
        b"".join(decrypt_stream(key, [b"\x00" * (HEADER_BYTES - 1)]))


def test_decrypt_stream_with_a_wiped_key_fails_closed() -> None:
    """🇺🇸 A key wiped before use raises `CryptoError`, not a silent open of garbage.

    An already-wiped `SecretBox` is a caller mistake (using key material
    after ending the session that owned it) that must still fail closed,
    exactly like a tampered ciphertext would.

    🇧🇷 Uma chave apagada antes do uso lança `CryptoError`, não abre lixo em silêncio.

    Uma `SecretBox` já apagada é um engano de quem chama (usar material de
    chave depois de encerrar a sessão dona dela) que ainda precisa falhar
    fechado, exatamente como um ciphertext adulterado.
    """
    key = SecretBox.random(32)
    encrypted = b"".join(encrypt_stream(secrets.token_bytes(32), [b"some content"]))
    key.wipe()

    with pytest.raises(CryptoError, match="header inválido"):
        b"".join(decrypt_stream(key, [encrypted]))


def test_decrypt_stream_rejects_a_cutoff_exactly_on_a_frame_boundary() -> None:
    """🇺🇸 A stream that ends right after a complete message frame, never reaching `TAG_FINAL`, is `CryptoError`.

    Distinct from `test_decrypt_stream_rejects_truncated_stream`
    (`test_roundtrips.py`), which cuts a few bytes out of the *middle* of the
    final frame: here every byte that *is* present parses as a
    fully-formed, correctly-authenticated frame — the stream is simply
    missing its closing `TAG_FINAL` frame outright, the "upload connection
    dropped between two parts" shape.

    🇧🇷 Um stream que termina logo depois de um frame de mensagem completo,
    sem nunca alcançar `TAG_FINAL`, é `CryptoError`.

    Diferente de `test_decrypt_stream_rejects_truncated_stream`
    (`test_roundtrips.py`), que corta alguns bytes do *meio* do frame final:
    aqui todo byte que *está* presente é interpretado como um frame completo
    e corretamente autenticado — o stream só está sem o frame de fechamento
    `TAG_FINAL` de vez, a forma "conexão do upload caiu entre duas partes".
    """
    key = secrets.token_bytes(32)
    plaintext = secrets.token_bytes(_SMALL_CHUNK * 2)  # 🇺🇸/🇧🇷 an exact multiple of the chunk size

    frames = list(encrypt_stream(key, [plaintext], chunk_size=_SMALL_CHUNK))
    # 🇺🇸/🇧🇷 header + 2 full-chunk message frames + the empty TAG_FINAL frame; drop only the last one.
    assert len(frames) == 4
    cut_off = b"".join(frames[:-1])

    with pytest.raises(CryptoError, match="TAG_FINAL ausente"):
        b"".join(decrypt_stream(key, [cut_off]))
