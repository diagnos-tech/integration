"""🇺🇸 `Drives`: the workspace's files — upload, list, name and download (`docs/PROTOCOL.md §9`).

Every file (DICOM, image, video, PDF) and every folder is a **node** of the
workspace, owned by exactly one security group. Each node has its own DEK,
wrapped for that group, and its name sealed under that DEK — so a node's
key never depends on anything but itself, and revoking a group is a matter
of the group's key, as with documents.

`_nodes.py` holds every byte of protocol (keys, staging, single and
multipart upload, SSE-C, download); `_source.py` turns any accepted input
into a named, known-size plaintext; `_drive.py` is the public face:
`vault.drives` for the whole workspace and `vault.drives.drive(group)` for
one group's files. Only the names re-exported below are public.

🇧🇷 `Drives`: os arquivos do workspace — subir, listar, nomear e baixar (`docs/PROTOCOL.md §9`).

Todo arquivo (DICOM, imagem, vídeo, PDF) e toda pasta é um **nó** do
workspace, de exatamente um security group. Cada nó tem a própria DEK,
embrulhada para esse grupo, e o nome selado sob essa DEK — então a chave de
um nó não depende de nada além dele mesmo, e revogar um grupo é questão da
chave do grupo, como nos documentos.

`_nodes.py` guarda todo byte de protocolo (chaves, reserva, upload único e
multipart, SSE-C, download); `_source.py` transforma qualquer entrada aceita
num texto claro nomeado e de tamanho conhecido; `_drive.py` é a face
pública: `vault.drives` para o workspace inteiro e
`vault.drives.drive(grupo)` para os arquivos de um grupo. Só os nomes
reexportados abaixo são públicos.
"""

from __future__ import annotations

from ._drive import Drive, Drives
from ._source import UploadSource

__all__ = ["Drive", "Drives", "UploadSource"]
