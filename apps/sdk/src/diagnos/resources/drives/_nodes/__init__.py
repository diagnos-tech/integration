"""🇺🇸 `_Nodes`: the one engine behind `vault.drives` — every byte of the `/nodes` protocol (`docs/PROTOCOL.md §9`).

It follows the web app's upload pipeline (`@repo/magic-files`) step for
step, so a file the SDK uploads is one the web app and the vault's
processor can open:

- **Keys.** Every node (file or folder) gets its own DEK, wrapped for its
  security group with `imgexam-node-dek-v1`; its name is sealed under that
  DEK with `imgexam-node-name-v1`. The body is sealed under a content key
  derived from the DEK, the node id and the `security_context` the vault
  returns at staging — the same derivation as documents (§7).
- **Body.** libsodium secretstream, 1 MiB chunks, `[len][frame]` framing;
  the declared size is computed before any byte is encrypted.
- **SSE-C.** R2's second layer uses the content key's *sister*
  (`derive_sse_c_key`), sent on the single `PUT`, on every multipart part
  and on the `GET`, exactly as the web app does.
- **Batches.** Up to 100 files per reservation; small files go up in one
  signed `PUT` and are confirmed together; large ones go up in parts,
  signed in waves of up to 200 as the upload advances.

This is a package, not a single module, so no file grows past the project's
~250-line convention: `_support.py` holds constants and pure data/algorithm
helpers; `_base.py` is shared construction plus the one read both directions
need; `_reading.py` is list/get/name/download; `_transfer.py` is the raw
single-`PUT`/multipart byte-moving; `_writing.py` is batching, staging and
folders, built on `_transfer.py`. `_Nodes` below stitches `_Reading` and
`_Writing` together, and implements `_seal_node` itself: a contract test
replaces this module's own `generate_dek`/`uuid` with a fixed double
(`monkeypatch.setattr(nodes_module, "generate_dek", ...)`), which only
`_seal_node` looking those up as *this* module's globals honours. Every name
importable from `diagnos.resources.drives._nodes` before this split —
including what tests assign onto `._stage`, or patch as `generate_dek`/
`uuid` — is re-exported/preserved here unchanged.

🇧🇷 `_Nodes`: o único motor por trás de `vault.drives` — todo byte do protocolo `/nodes` (`docs/PROTOCOL.md §9`).

Segue o pipeline de upload do app web (`@repo/magic-files`) passo a passo,
para um arquivo que o SDK sobe ser um que o app web e o processador do
cofre conseguem abrir:

- **Chaves.** Todo nó (arquivo ou pasta) ganha a própria DEK, embrulhada
  para o security group com `imgexam-node-dek-v1`; o nome é selado sob
  essa DEK com `imgexam-node-name-v1`. O corpo é selado sob uma chave de
  conteúdo derivada da DEK, do id do nó e do `security_context` que o
  cofre devolve na reserva — a mesma derivação dos documentos (§7).
- **Corpo.** secretstream da libsodium, chunks de 1 MiB, enquadramento
  `[len][frame]`; o tamanho declarado é calculado antes de cifrar um byte.
- **SSE-C.** A segunda camada do R2 usa a *irmã* da chave de conteúdo
  (`derive_sse_c_key`), mandada no `PUT` único, em toda parte de multipart
  e no `GET`, exatamente como o app web faz.
- **Lotes.** Até 100 arquivos por reserva; arquivos pequenos sobem num
  `PUT` assinado e são confirmados juntos; os grandes sobem por partes,
  assinadas em ondas de até 200 conforme o upload avança.

Isto é um pacote, não um módulo único, para nenhum arquivo passar da
convenção de ~250 linhas do projeto: `_support.py` guarda constantes e
ajudantes de dado/algoritmo puros; `_base.py` é a construção compartilhada
mais a leitura de que as duas direções precisam; `_reading.py` é
listar/buscar/nomear/baixar; `_transfer.py` é o `PUT` único/multipart cru de
mover bytes; `_writing.py` é lote, reserva e pastas, construído sobre
`_transfer.py`. `_Nodes` abaixo costura `_Reading` e `_Writing` juntas, e
implementa `_seal_node` ela mesma: um teste de contrato substitui o
`generate_dek`/`uuid` deste próprio módulo por um duplo fixo
(`monkeypatch.setattr(nodes_module, "generate_dek", ...)`), o que só
`_seal_node` buscando-os como globais *deste* módulo respeita. Todo nome
importável de `diagnos.resources.drives._nodes` antes desta divisão —
inclusive o que testes atribuem em `._stage`, ou substituem como
`generate_dek`/`uuid` — é reexportado/preservado aqui sem mudanças.
"""

from __future__ import annotations

import uuid
from typing import Any

from diagnos.crypto import NODE_DEK_INFO, NODE_NAME_INFO, SecretBox, encrypt_content, generate_dek, wrap_key

from ._reading import _Reading
from ._support import DEFAULT_PAGE_SIZE, UploadInput
from ._writing import _Writing

__all__ = ["DEFAULT_PAGE_SIZE", "UploadInput", "_Nodes"]


class _Nodes(_Reading, _Writing):
    """🇺🇸 The `/nodes` routes of one workspace: list, read, name, download, upload, folders.

    Assembled from `_Reading` and `_Writing` (both built on `_NodesBase` for
    construction); `_seal_node` is the one method defined here rather than
    inherited — see `_base.py`'s declaration of it for why (a contract test
    monkeypatches this module's own `generate_dek`/`uuid`). Everything else
    exists so the two halves have one name and one instance, exactly as
    `_Nodes` did before this split (`Drive`/`Drives` in `_drive.py` still
    hold one `_Nodes` each, and a test replacing `._stage` on that one
    instance still reaches the method `_upload_batch` calls).

    🇧🇷 As rotas `/nodes` de um workspace: listar, ler, nomear, baixar, subir, pastas.

    Montada a partir de `_Reading` e `_Writing` (ambas construídas sobre
    `_NodesBase` para a construção); `_seal_node` é o único método definido
    aqui em vez de herdado — veja a declaração dele em `_base.py` para o
    porquê (um teste de contrato substitui o `generate_dek`/`uuid` deste
    próprio módulo). O resto existe para as duas metades terem um nome e uma
    instância só, exatamente como `_Nodes` fazia antes desta divisão
    (`Drive`/`Drives` em `_drive.py` ainda guardam um `_Nodes` cada, e um
    teste que substitui `._stage` nessa mesma instância ainda alcança o
    método que `_upload_batch` chama).
    """

    def _seal_node(self, group_key: SecretBox, security_group: str, name: str) -> tuple[SecretBox, dict[str, Any]]:
        """🇺🇸 A fresh node DEK plus the sealed name and wrapped key every stage entry carries.

        🇧🇷 Uma DEK de nó nova mais o nome selado e a chave embrulhada que toda entrada de reserva leva.
        """
        dek = generate_dek(self._entropy)
        entry = {
            "client_ref": uuid.uuid4().hex,
            "encrypted_name": encrypt_content(dek, name.encode("utf-8"), NODE_NAME_INFO).to_dict(),
            "encrypted_keys": {security_group: wrap_key(group_key, dek, NODE_DEK_INFO).to_dict()},
        }
        return dek, entry
