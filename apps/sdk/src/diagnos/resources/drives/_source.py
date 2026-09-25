"""🇺🇸 Turns any `upload()`/`upload_many()` input into a named, known-size, reopenable plaintext.

🇧🇷 Transforma qualquer entrada de `upload()`/`upload_many()` num texto claro nomeado, de tamanho conhecido e reabrível.
"""

from __future__ import annotations

import io
import mimetypes
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Final

# 🇺🇸 Extensions `mimetypes` does not know but the vault's media pipeline cares about (`media_kind`).
# 🇧🇷 Extensões que o `mimetypes` não conhece mas que importam para o pipeline de mídia do cofre (`media_kind`).
_EXTRA_MIME_TYPES: Final[dict[str, str]] = {".dcm": "application/dicom", ".dicom": "application/dicom"}


def _no_cleanup() -> None:
    """🇺🇸 The default `_PlaintextSource.cleanup`: nothing to remove.

    🇧🇷 O `_PlaintextSource.cleanup` padrão: nada para remover.
    """


@dataclass
class _PlaintextSource:
    """🇺🇸 A known plaintext size plus a reader that can be reopened.

    Encryption reads the file exactly once, but a multi-file batch needs
    every source open in turn, and the size must be known before staging.

    🇧🇷 Um tamanho de texto claro conhecido mais um leitor que pode ser reaberto.

    A cifragem lê o arquivo uma única vez, mas um lote com vários arquivos
    precisa abrir cada fonte por sua vez, e o tamanho precisa ser conhecido
    antes da reserva.
    """

    size: int
    open: Callable[[], BinaryIO]
    cleanup: Callable[[], None] = field(default=_no_cleanup)


def _plaintext_source(source: str | os.PathLike[str] | bytes | BinaryIO) -> _PlaintextSource:
    """🇺🇸 Normalizes any accepted `upload()` input into a `_PlaintextSource`.

    A path or `bytes` already knows its size. A bare file-like object
    generally does not (it may not even be seekable) — and a single `PUT`
    is signed for an exact size, known before staging. Spooling such a
    stream to a temporary file once turns it into the "path" case.

    🇧🇷 Normaliza qualquer entrada aceita por `upload()` num `_PlaintextSource`.

    Um path ou `bytes` já sabe o próprio tamanho. Um objeto tipo-arquivo cru
    em geral não sabe (pode nem ser seekable) — e um `PUT` único é assinado
    para um tamanho exato, conhecido antes da reserva. Derramar esse stream
    uma vez num arquivo temporário o transforma no caso "path".
    """
    if isinstance(source, bytes):
        data = source
        return _PlaintextSource(size=len(data), open=lambda: io.BytesIO(data))
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        return _PlaintextSource(size=path.stat().st_size, open=lambda: path.open("rb"))
    return _spool_to_temp_file(source)


def _spool_to_temp_file(handle: BinaryIO) -> _PlaintextSource:
    """🇺🇸 Copies an arbitrary readable stream to disk once, so its size becomes known and re-openable.

    🇧🇷 Copia um stream legível qualquer para o disco uma vez, para o tamanho ficar conhecido e reabrível.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False)
    try:
        shutil.copyfileobj(handle, tmp)
    finally:
        tmp.close()
    path = Path(tmp.name)
    return _PlaintextSource(
        size=path.stat().st_size,
        open=lambda: path.open("rb"),
        cleanup=lambda: path.unlink(missing_ok=True),
    )


def guess_mime_type(name: str) -> str | None:
    """🇺🇸 The MIME type a browser would send for `name`, DICOM included; `None` when unknown.

    🇧🇷 O tipo MIME que um navegador mandaria para `name`, DICOM incluído; `None` quando desconhecido.
    """
    suffix = Path(name).suffix.lower()
    if suffix in _EXTRA_MIME_TYPES:
        return _EXTRA_MIME_TYPES[suffix]
    guessed, _encoding = mimetypes.guess_type(name, strict=False)
    return guessed


@dataclass(frozen=True)
class UploadSource:
    """🇺🇸 One file for `upload_many`: the content plus its name and MIME type.

    `name` defaults to the file name of a path (or of an open file); a
    `bytes` or anonymous stream needs one explicitly — every node carries a
    sealed name. `mime_type` defaults to a guess from the name, which is
    what lets the vault classify DICOM, images and video.

    🇧🇷 Um arquivo para `upload_many`: o conteúdo mais o nome e o tipo MIME.

    `name` é, por padrão, o nome de arquivo de um path (ou de um arquivo
    aberto); `bytes` ou um stream anônimo precisam de um explícito — todo nó
    leva um nome selado. `mime_type` é, por padrão, um palpite pelo nome, o
    que deixa o cofre classificar DICOM, imagem e vídeo.
    """

    source: str | os.PathLike[str] | bytes | BinaryIO
    name: str | None = None
    mime_type: str | None = None

    def resolved_name(self) -> str:
        """🇺🇸 The explicit name, else the path's or open file's base name.

        🇧🇷 O nome explícito, senão o nome base do path ou do arquivo aberto.
        """
        if self.name:
            return self.name
        if isinstance(self.source, (str, os.PathLike)):
            return Path(self.source).name
        handle_name = getattr(self.source, "name", None)
        if isinstance(handle_name, str) and handle_name:
            return Path(handle_name).name
        raise ValueError(
            "this upload has no file name: pass name=... for bytes or an anonymous stream · este upload não tem nome "
            "de arquivo: passe name=... para bytes ou um stream anônimo"
        )

    def resolved_mime_type(self, name: str) -> str | None:
        """🇺🇸 The explicit MIME type, else a guess from `name`.

        🇧🇷 O tipo MIME explícito, senão um palpite por `name`.
        """
        return self.mime_type or guess_mime_type(name)
