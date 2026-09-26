"""🇺🇸 Constants, the batch-upload input type, and small free helpers the write path builds on.

`_PreparedUpload` and `_group_into_parts` are pure data/algorithm — no
`self`, no network — so they live apart from `_Writing` (`_writing.py`)
itself, and the vault's own batch/part limits (`services/uploads/policy.ts`,
§13) are named once here instead of scattered across call sites.

🇧🇷 Constantes, o tipo de entrada de upload em lote, e pequenos ajudantes livres em que o caminho de escrita se apoia.

`_PreparedUpload` e `_group_into_parts` são dado/algoritmo puro — sem
`self`, sem rede — então vivem à parte de `_Writing` (`_writing.py`) em si,
e os próprios limites de lote/parte do cofre
(`services/uploads/policy.ts`, §13) são nomeados uma única vez aqui, em vez
de espalhados pelos pontos de chamada.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, BinaryIO, Final

from diagnos.crypto import SecretBox

from .._source import UploadSource
from .._source import _PlaintextSource as _PlaintextSource

# 🇺🇸 The vault's own limits (`services/uploads/policy.ts`, §13).
# 🇧🇷 Os limites do próprio cofre (`services/uploads/policy.ts`, §13).
MAX_FILES_PER_BATCH: Final[int] = 100
MAX_IDS_PER_COMPLETE_CALL: Final[int] = 200
MAX_PARTS_PER_SIGN_REQUEST: Final[int] = 200
DEFAULT_PAGE_SIZE: Final[int] = 50

UploadInput = UploadSource | str | os.PathLike[str] | bytes | BinaryIO


@dataclass
class _PreparedUpload:
    """🇺🇸 One file, ready to stage: its plaintext, its fresh DEK and everything the reservation carries.

    🇧🇷 Um arquivo, pronto para a reserva: o texto claro, a DEK nova e tudo o que a reserva leva.
    """

    client_ref: str
    plaintext: _PlaintextSource
    dek: SecretBox
    stage_entry: dict[str, Any]

    @property
    def encrypted_bytes(self) -> int:
        """🇺🇸 The size declared at staging (the sealed, framed body). 🇧🇷 O tamanho declarado na reserva."""
        return int(self.stage_entry["size"])


def _group_into_parts(chunks: Iterable[bytes], part_size: int) -> Iterator[tuple[int, bytes]]:
    """🇺🇸 Cuts the framed ciphertext into fixed-size multipart parts, 1-indexed — a cut, not a second encryption.

    🇧🇷 Corta o ciphertext enquadrado em partes de multipart de tamanho fixo, a partir de 1 — um corte, não
    outra cifragem.
    """
    buffer = bytearray()
    part_number = 1
    for chunk in chunks:
        buffer.extend(chunk)
        while len(buffer) >= part_size:
            yield part_number, bytes(buffer[:part_size])
            del buffer[:part_size]
            part_number += 1
    if buffer:
        yield part_number, bytes(buffer)
