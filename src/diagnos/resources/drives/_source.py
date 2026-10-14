"""Turns any `upload()` or `upload_many()` input into a named, known-size, reopenable plaintext."""

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

# Extensions `mimetypes` does not know but the vault's media pipeline cares about (`media_kind`).
_EXTRA_MIME_TYPES: Final[dict[str, str]] = {".dcm": "application/dicom", ".dicom": "application/dicom"}


def _no_cleanup() -> None:
    """Do nothing; the default `_PlaintextSource.cleanup`, for sources with nothing to remove."""


@dataclass
class _PlaintextSource:
    """A known plaintext size plus a reader that can be reopened.

    Encryption reads the file exactly once, but a multi-file batch needs
    every source open in turn, and the size must be known before staging.
    """

    size: int
    open: Callable[[], BinaryIO]
    cleanup: Callable[[], None] = field(default=_no_cleanup)


def _plaintext_source(source: str | os.PathLike[str] | bytes | BinaryIO) -> _PlaintextSource:
    """Normalize any accepted `upload()` input into a `_PlaintextSource`.

    A path or `bytes` already knows its size. A bare file-like object
    generally does not (it may not even be seekable), and a single `PUT`
    is signed for an exact size, known before staging. Spooling such a
    stream to a temporary file once turns it into the "path" case.
    """
    if isinstance(source, bytes):
        data = source
        return _PlaintextSource(size=len(data), open=lambda: io.BytesIO(data))
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        return _PlaintextSource(size=path.stat().st_size, open=lambda: path.open("rb"))
    return _spool_to_temp_file(source)


def _spool_to_temp_file(handle: BinaryIO) -> _PlaintextSource:
    """Copy an arbitrary readable stream to disk once, so that its size becomes known and it can be reopened."""
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
    """Guess the MIME type a browser would send for `name`, DICOM included.

    Args:
        name: The file name.

    Returns:
        The MIME type, or `None` when unknown.
    """
    suffix = Path(name).suffix.lower()
    if suffix in _EXTRA_MIME_TYPES:
        return _EXTRA_MIME_TYPES[suffix]
    guessed, _encoding = mimetypes.guess_type(name, strict=False)
    return guessed


@dataclass(frozen=True)
class UploadSource:
    """One file for `upload_many`: the content plus its name and MIME type.

    `name` defaults to the file name of a path (or of an open file). A
    `bytes` or anonymous stream needs one explicitly, because every node
    carries a sealed name. `mime_type` defaults to a guess from the name,
    which is what lets the vault classify DICOM, images and video.

    Attributes:
        source: A path, the file's bytes, or an open binary file.
        name: The file name to seal; see above for the default.
        mime_type: The MIME type; see above for the default.
    """

    source: str | os.PathLike[str] | bytes | BinaryIO
    name: str | None = None
    mime_type: str | None = None

    def resolved_name(self) -> str:
        """Return the explicit name, else the path's or open file's base name.

        Raises:
            ValueError: If neither the source nor `name` provides a file name.
        """
        if self.name:
            return self.name
        if isinstance(self.source, (str, os.PathLike)):
            return Path(self.source).name
        handle_name = getattr(self.source, "name", None)
        if isinstance(handle_name, str) and handle_name:
            return Path(handle_name).name
        raise ValueError("this upload has no file name: pass name=... for bytes or an anonymous stream")

    def resolved_mime_type(self, name: str) -> str | None:
        """Return the explicit MIME type, else a guess from `name`."""
        return self.mime_type or guess_mime_type(name)
