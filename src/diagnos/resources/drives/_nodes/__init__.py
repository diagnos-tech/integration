"""`_Nodes`: the one engine behind `vault.drives`, holding every byte of the `/nodes` protocol (`docs/PROTOCOL.md §9`).

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

This is a package, not a single module, so that no file grows past the
project's file-size limit. `_support.py` holds constants and pure data and
algorithm helpers. `_base.py` is shared construction plus the one read both
directions need. `_reading.py` is list, get, name and download.
`_transfer.py` is the raw single-`PUT` and multipart byte-moving.
`_writing.py` is batching, staging and folders, built on `_transfer.py`.
`_Nodes` below stitches `_Reading` and `_Writing` together.
"""

from __future__ import annotations

from ._reading import _Reading
from ._support import DEFAULT_PAGE_SIZE, UploadInput
from ._writing import _Writing

__all__ = ["DEFAULT_PAGE_SIZE", "UploadInput", "_Nodes"]


class _Nodes(_Reading, _Writing):
    """The `/nodes` routes of one workspace: list, read, name, download, upload and folders.

    There is one instance per `Drives` (`_drive.py`), shared by every `Drive`
    it hands out, so that both halves share a transport, a keyring and the
    vault's `security_context` handling.
    """
