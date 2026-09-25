"""🇺🇸 Turns any `upload()`/`upload_many()` input into a known-size, reopenable plaintext.

🇧🇷 Transforma qualquer entrada de `upload()`/`upload_many()` num texto claro de tamanho conhecido e reabrível.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from diagnos.crypto import EncryptedPayload


def _no_cleanup() -> None:
    """🇺🇸 The default `_PlaintextSource.cleanup`: nothing to remove.

    🇧🇷 O `_PlaintextSource.cleanup` padrão: nada para remover.
    """


@dataclass
class _PlaintextSource:
    """🇺🇸 A known plaintext size plus a reader that can be reopened.

    Encryption reads the file exactly once, but a caller retrying a failed
    upload — or a multi-file batch that needs every source open in turn —
    needs the option to open it again.

    🇧🇷 Um tamanho de texto claro conhecido mais um leitor que pode ser reaberto.

    A cifragem lê o arquivo uma única vez, mas quem chama retentando um
    upload que falhou — ou um lote com vários arquivos, que precisa abrir
    cada fonte por sua vez — precisa da opção de abrir de novo.
    """

    size: int
    open: Callable[[], BinaryIO]
    cleanup: Callable[[], None] = field(default=_no_cleanup)


def _plaintext_source(source: str | os.PathLike[str] | bytes | BinaryIO) -> _PlaintextSource:
    """🇺🇸 Normalizes any accepted `upload()` input into a `_PlaintextSource`.

    A path or `bytes` already knows its size for free. A bare file-like
    object generally does not (it may not even be seekable) — and
    `docs/PROTOCOL.md §9`'s single-PUT signature locks `content-length`
    up front, so the exact encrypted size has to be known *before* staging.
    Spooling such a stream to a temporary file once, up front, turns the
    "unknown size" case into the "path" case for the rest of the upload
    pipeline instead of threading a special case through it.

    🇧🇷 Normaliza qualquer entrada aceita por `upload()` num `_PlaintextSource`.

    Um path ou `bytes` já sabe o próprio tamanho de graça. Um objeto tipo-arquivo
    cru geralmente não sabe (pode nem ser seekable) — e a assinatura de PUT
    único de `docs/PROTOCOL.md §9` trava o `content-length` de antemão, então
    o tamanho cifrado exato precisa ser conhecido *antes* da reserva. Derramar
    esse stream numa vez, de antemão, num arquivo temporário transforma o caso
    "tamanho desconhecido" no caso "path" para o resto do pipeline de upload,
    em vez de espalhar um caso especial por ele.
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


@dataclass(frozen=True)
class UploadSource:
    """🇺🇸 One file for `Drive.upload_many`, carrying the per-file `name`/`mime_type` `upload()` takes as keyword args.

    🇧🇷 Um arquivo para `Drive.upload_many`, carregando o `name`/`mime_type`
    por arquivo que `upload()` recebe como argumento nomeado.
    """

    source: str | os.PathLike[str] | bytes | BinaryIO
    name: str | None = None
    mime_type: str | None = None


@dataclass
class _PreparedUpload:
    """🇺🇸 One file, past normalization: its plaintext source plus everything the stage request needs.

    🇧🇷 Um arquivo, já normalizado: sua fonte de texto claro mais tudo que a requisição de reserva precisa.
    """

    client_ref: str
    plaintext: _PlaintextSource
    encrypted_bytes: int
    mime_type: str | None
    encrypted_name: EncryptedPayload | None

    def to_stage_file(self) -> dict[str, Any]:
        """🇺🇸 The `files[]` entry `POST {base}/uploads` expects for this file.

        🇧🇷 A entrada de `files[]` que `POST {base}/uploads` espera para este arquivo.
        """
        stage_file: dict[str, Any] = {"client_ref": self.client_ref, "size": self.encrypted_bytes}
        if self.mime_type is not None:
            stage_file["mime_type"] = self.mime_type
        if self.encrypted_name is not None:
            stage_file["encrypted_name"] = self.encrypted_name.to_dict()
        return stage_file
