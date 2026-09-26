"""🇺🇸 `_NodesBase`: the construction state, and the one read both `_Reading` and `_Writing` need.

🇧🇷 `_NodesBase`: o estado de construção, e a leitura de que `_Reading` e `_Writing` precisam.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from diagnos.crypto import EntropyMixer, SecretBox
from diagnos.models import DriveNode
from diagnos.session.keyring import Keyring

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport


class _NodesBase:
    """🇺🇸 Shared constructor for the `/nodes` routes of one workspace.

    🇧🇷 Construtor compartilhado das rotas `/nodes` de um workspace.
    """

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
    ) -> None:
        """🇺🇸 `keyring_provider` is asked fresh on every call, like `VersionedDocuments`.

        🇧🇷 `keyring_provider` é consultado a cada chamada, como em `VersionedDocuments`.
        """
        self._transport = transport
        self._keyring_provider = keyring_provider
        self._entropy = entropy
        self._base = f"/api/external/v1/workspaces/{workspace_id}/nodes"

    def get(self, node_id: str) -> DriveNode:
        """🇺🇸 One ready file's index (`GET /nodes/{id}`); folders and unfinished uploads answer `404`.

        Shared by `_Reading` (the public route) and `_Writing._upload_batch`
        (which fetches a confirmed node the vault did not echo back).

        🇧🇷 O índice de um arquivo pronto (`GET /nodes/{id}`); pastas e uploads inacabados respondem `404`.

        Compartilhado por `_Reading` (a rota pública) e
        `_Writing._upload_batch` (que busca um nó confirmado que o cofre
        não ecoou).
        """
        result = self._transport.get(f"{self._base}/{node_id}")
        return DriveNode.model_validate(result["node"])

    def _seal_node(self, group_key: SecretBox, security_group: str, name: str) -> tuple[SecretBox, dict[str, Any]]:
        """🇺🇸 Declared here for `_Writing` to call, implemented on `_Nodes` itself (`__init__.py`).

        The implementation needs `generate_dek`/`uuid` as *this class's own*
        module globals, not `_writing.py`'s: a contract test replaces
        `diagnos.resources.drives._nodes.generate_dek`/`.uuid` (the package's
        `__init__.py`) with a fixed double, and a lookup from a different
        module's globals would not see that swap. `_Writing.create_folder`/
        `_prepare` still reach the override through `self._seal_node(...)` —
        Python resolves that by the instance's class, not by where the
        calling method is defined.

        🇧🇷 Declarado aqui para `_Writing` chamar, implementado no próprio `_Nodes` (`__init__.py`).

        A implementação precisa de `generate_dek`/`uuid` como globais do
        *próprio módulo dela*, não de `_writing.py`: um teste de contrato
        substitui `diagnos.resources.drives._nodes.generate_dek`/`.uuid` (o
        `__init__.py` do pacote) por um duplo fixo, e uma busca a partir dos
        globais de outro módulo não veria essa troca. `_Writing.create_folder`/
        `_prepare` ainda alcançam a substituição via `self._seal_node(...)` —
        o Python resolve isso pela classe da instância, não por onde o
        método que chama foi definido.
        """
        raise NotImplementedError
