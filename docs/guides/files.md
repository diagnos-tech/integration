# Files and folders

**English** · [Português (Brasil)](files.pt-BR.md)

`vault.drives` stores DICOM series, images, video and PDFs end-to-end encrypted, in folders and linked to exams.
Each file gets its own key; its name, its content and the storage layer's own encryption are all sealed exactly the
way the web app seals them, so a file uploaded here opens in the web app and the other way round. The model — nodes,
groups, pending and ready — is in [Concepts](concepts.md#files-and-folders-nodes).

## Upload

A **drive** is the files of one security group. Writing needs one; reading needs only a node id.

```python
from diagnos import Diagnos

vault = Diagnos()
drive = vault.drives.drive("sg_oncology")

node = drive.upload("scans/IM-0001.dcm")  # name and MIME type from the path
print(node.node_id, node.status, node.mime_type, node.size)

note = drive.upload(b"raw bytes work too", name="note.txt")  # bytes need a name
with open("report.pdf", "rb") as handle:
    pdf = drive.upload(handle)  # an open file: its name comes from the handle
```

| Argument | Default | |
|---|---|---|
| `name` | the path's (or open file's) file name | required for `bytes` and anonymous streams; sealed |
| `mime_type` | guessed from the name; `.dcm` is `application/dicom` | sent in clear — it is how the vault classifies DICOM, images and video |
| `exam_id` | none | links the file to an exam |
| `parent_id` | none | the folder to put it in |

`upload()` returns once the file is confirmed: the node is `ready`.

> [!TIP]
> Pass a path or `bytes` when you can. A size must be known before encrypting — the vault signs each upload for an
> exact number of bytes — so any other stream is first copied to a temporary file, in plain text, and removed after
> the upload.

### Many files at once

```python
from diagnos import UploadSource

folder_id = drive.create_folder("CT 2026-09-01")
nodes = drive.upload_many(
    ["scans/IM-0001.dcm", "scans/IM-0002.dcm", UploadSource(b"...", name="series-notes.txt")],
    parent_id=folder_id,
)
print([drive.name_of(node) for node in nodes])  # in input order, all ready
```

`upload_many` reserves up to 100 files per round trip and returns the nodes in input order. It blocks until each
batch is done; there is no per-byte progress callback yet.

### How big files travel

You never choose; the vault does, by size:

| Size | How it goes up |
|---|---|
| up to 64 MiB | one signed `PUT`, confirmed together with the rest of its batch |
| above 64 MiB, up to 50 GiB | 32 MiB parts, signed in waves of up to 200 as the upload advances |

A multipart upload that fails midway is aborted, so the vault releases the reserved space at once; an abandoned
reservation expires after 6 hours. The body is encrypted in 1 MiB frames as it streams, so memory stays flat
whatever the file size. [PROTOCOL.md §9](../PROTOCOL.md#9-files-and-folders-nodes) has the byte layout.

## Folders

```python
series = drive.create_folder("Series 2", parent_id=folder_id)  # nested
drive.upload("scans/IM-0002.dcm", parent_id=series)
```

`create_folder` returns the new folder's node id. The vault only sees sealed names, so it cannot tell two folders
with the same name apart: calling it twice creates two folders. Folders are ready at once — they have no content.

## List

```python
for child in drive.iter_all(parent_id=folder_id):  # one folder of this group
    print(drive.name_of(child), child.kind, child.size)

for item in vault.drives.iter_all(include_pending=True):  # every group this session may list
    print(item.security_group_id, item.status, item.node_id)

page = vault.drives.list(security_group="sg_oncology", limit=50)  # one page
```

`drive.list()`/`iter_all()` walk one group; `vault.drives.list()`/`iter_all()` walk every group this session may
list, filtered by `security_group`, `exam_id`, `parent_id` or `include_pending`. Rows are `DriveNode`s — metadata
only. Names stay sealed until you ask: `name_of(node)` opens one, so a page of a thousand files costs no decryption
you did not want.

> [!WARNING]
> A name is whatever the uploader sealed, and the web app seals a **relative path** there
> (`exams/2026/IM-0001.dcm`). Never use it as a local path as-is: take its last segment, as the CLI and the API do.

`vault.drives.get(node_id)` returns one ready file's metadata; a folder or a pending upload answers
`NotFoundError` — there is nothing to download.

## Download

```python
data = vault.drives.download(node.node_id)  # the whole file, decrypted, in RAM
vault.drives.download(node.node_id, "IM-0001.dcm")  # straight to a file, one chunk in RAM at a time

with open("copy.dcm", "wb") as out:
    for chunk in vault.drives.iter_download(node.node_id):  # stream it yourself
        out.write(chunk)
```

`iter_download` decrypts lazily: the first bytes reach you before the last ones leave storage, and nothing larger
than one 1 MiB frame is ever held. Every frame is authenticated; a tampered or truncated file raises `CryptoError`
instead of returning damaged bytes.

## What the vault sees about a file

The node id, its group, the exam and folder it is linked to, its MIME type, its size (of the encrypted body, which
the vault measures and bills by) and timestamps. Never its name, never its content. The full list is in the
[security model](security.md#what-the-vault-sees).

## What is not here yet

- Delete, move and rename have no external route yet.
- Thumbnails and web-friendly transcodes (`optimized_variants`) are produced only for files whose key is also escrowed
  for the vault's media processor, which neither the web app nor the SDK does today.
- No per-byte progress callback.

Details and the questions still open on the vault side: [COMPATIBILITY.md](../COMPATIBILITY.md#files-and-folders).
