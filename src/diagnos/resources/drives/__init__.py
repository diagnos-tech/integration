"""`Drives`: the workspace's files, with upload, list, name and download (`docs/PROTOCOL.md §9`).

Every file (DICOM, image, video, PDF) and every folder is a **node** of the
workspace, owned by exactly one security group. Each node has its own DEK,
wrapped for that group, and its name sealed under that DEK. A node's key
therefore never depends on anything but itself, and revoking a group is a
matter of the group's key, as with documents.

`_nodes.py` holds every byte of protocol (keys, staging, single and
multipart upload, SSE-C, download). `_source.py` turns any accepted input
into a named, known-size plaintext. `_drive.py` is the public face:
`vault.drives` for the whole workspace and `vault.drives.drive(group)` for
one group's files. Only the names re-exported below are public.
"""

from __future__ import annotations

from ._drive import Drive, Drives
from ._source import UploadSource

__all__ = ["Drive", "Drives", "UploadSource"]
