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
`_Writing` together.

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
`_transfer.py`. `_Nodes` abaixo costura `_Reading` e `_Writing` juntas.
"""

from __future__ import annotations

from ._reading import _Reading
from ._support import DEFAULT_PAGE_SIZE, UploadInput
from ._writing import _Writing

__all__ = ["DEFAULT_PAGE_SIZE", "UploadInput", "_Nodes"]


class _Nodes(_Reading, _Writing):
    """🇺🇸 The `/nodes` routes of one workspace: list, read, name, download, upload, folders.

    One instance per `Drive`/`Drives` (`_drive.py`), so both halves share a
    transport, a keyring and the vault's `security_context` handling.

    🇧🇷 As rotas `/nodes` de um workspace: listar, ler, nomear, baixar, subir, pastas.

    Uma instância por `Drive`/`Drives` (`_drive.py`), para as duas metades
    dividirem transporte, keyring e o tratamento do `security_context` do cofre.
    """
