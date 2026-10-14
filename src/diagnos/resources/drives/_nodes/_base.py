"""`_NodesBase`: the construction state, and the one read both `_Reading` and `_Writing` need."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from diagnos.crypto import EntropyMixer
from diagnos.models import DriveNode
from diagnos.session.keyring import Keyring

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport


class _NodesBase:
    """Shared constructor for the `/nodes` routes of one workspace."""

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
    ) -> None:
        """Bind the engine to one workspace.

        `keyring_provider` is asked fresh on every call, like in `VersionedDocuments`.

        Args:
            transport: The signed HTTP transport.
            keyring_provider: Returns the live keyring, unlocking the session on first use.
            entropy: The process's entropy mixer, used for new DEKs.
            workspace_id: The workspace whose nodes are addressed.
        """
        self._transport = transport
        self._keyring_provider = keyring_provider
        self._entropy = entropy
        self._base = f"/api/external/v1/workspaces/{workspace_id}/nodes"

    def get(self, node_id: str) -> DriveNode:
        """Fetch one ready file's index (`GET /nodes/{id}`); folders and unfinished uploads answer `404`.

        This is shared by `_Reading` (the public route) and
        `_Writing._upload_batch` (which fetches a confirmed node the vault did
        not echo back).

        Args:
            node_id: The node to fetch.

        Returns:
            The node's index.

        Raises:
            NotFoundError: If the node is a folder, an unfinished upload, or does not exist.
        """
        self._keyring_provider()  # lazy unlock before signing (see `list`)
        result = self._transport.get(f"{self._base}/{node_id}")
        return DriveNode.model_validate(result["node"])
