"""🇺🇸 `Drives`: upload and download files against a security group (`docs/PROTOCOL.md §9`).

A "drive" is a security group — every file (DICOM, image, video, PDF) is a
**node** whose key derives from that group's DEK (`derive_node_key`), so
there is never a wrapped key to carry per file: revocation happens once, at
the group, and every derived node key dies with it.

`node_key` only exists once the vault hands back a `node_id` (staging is
what creates it), which looks at first like it blocks encrypting
`encrypted_name` up front too — `docs/PROTOCOL.md §9`'s
`node_key = HKDF(group_dek, salt=node_id, ...)` would make the name
depend on an id the SDK does not have yet when it builds the very request
that asks for one. It does not, because `encrypted_name` is wrapped under
the **group** DEK directly (`wrap_key(group_dek, name, NODE_NAME_INFO)`),
never under `node_key` — the same key `Drive.name_of` unwraps it with later,
needing only the security group, not any particular node. That is what lets
`encrypted_name` travel inside the very first `POST {base}/uploads` request,
alongside `size`/`mime_type`, instead of needing a follow-up rename call
after `node_id` exists. (`docs/PROTOCOL.md §9` should say `group_dek`, not
`node_key`, for `encrypted_name` — flagged for the document to be corrected.)

This package splits the one responsibility across files: `_source.py` turns
any accepted `upload()` input into a known-size, reopenable plaintext;
`_upload.py` stages and `PUT`s it (single or multipart); `_download.py`
downloads, decrypts and names a node; `_drive.py` is the `Drive`/`Drives`
facade that ties the three together. Only the names re-exported below are
meant to be imported from outside this package.

🇧🇷 `Drives`: upload e download de arquivos contra um security group
(`docs/PROTOCOL.md §9`).

Um "drive" é um security group — todo arquivo (DICOM, imagem, vídeo, PDF) é
um **nó** cuja chave deriva da DEK daquele grupo (`derive_node_key`), então
nunca existe uma chave embrulhada por arquivo para carregar: a revogação
acontece uma vez, no grupo, e toda chave de nó derivada morre junto.

`node_key` só existe depois que o cofre devolve um `node_id` (é a reserva
que o cria), o que à primeira vista parece travar cifrar `encrypted_name` de
antemão também — o `node_key = HKDF(group_dek, salt=node_id, ...)` de
`docs/PROTOCOL.md §9` faria o nome depender de um id que o SDK ainda não tem
ao montar a própria requisição que pede um. Não trava, porque
`encrypted_name` é embrulhado sob a DEK do **grupo** direto
(`wrap_key(group_dek, name, NODE_NAME_INFO)`), nunca sob `node_key` — a
mesma chave que `Drive.name_of` usa para desembrulhar depois, precisando só
do security group, não de nó nenhum em particular. É isso que deixa
`encrypted_name` viajar dentro da própria primeira requisição
`POST {base}/uploads`, junto de `size`/`mime_type`, em vez de precisar de
uma chamada de renomear depois que o `node_id` existe. (`docs/PROTOCOL.md
§9` deveria dizer `group_dek`, não `node_key`, para `encrypted_name` —
sinalizado para o documento ser corrigido.)

Este pacote divide a responsabilidade única entre arquivos: `_source.py`
transforma qualquer entrada aceita por `upload()` num texto claro de
tamanho conhecido e reabrível; `_upload.py` reserva e faz `PUT` dele (single
ou multipart); `_download.py` baixa, decifra e nomeia um nó; `_drive.py` é a
fachada `Drive`/`Drives` que junta os três. Só os nomes reexportados abaixo
são para ser importados de fora deste pacote.
"""

from __future__ import annotations

from ._drive import Drive, Drives
from ._source import UploadSource

__all__ = ["Drive", "Drives", "UploadSource"]
