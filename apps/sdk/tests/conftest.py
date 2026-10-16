"""🇺🇸 Shared test fixtures: the path to the normative protocol vectors, and no real keyring.

🇧🇷 Fixtures compartilhadas de teste: o caminho dos vetores normativos do protocolo, e nenhum chaveiro de verdade.
"""

from __future__ import annotations

from pathlib import Path

import keyring
import pytest
from keyring.backends import fail

VECTORS = Path(__file__).parent / "vectors"


@pytest.fixture(autouse=True)
def _no_system_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `Settings.from_env()` looks in the keyring; a test must never read (or write) the developer's own.

    🇧🇷 O `Settings.from_env()` procura no chaveiro; um teste nunca pode ler (nem gravar) o de quem o roda.
    """
    monkeypatch.setattr(keyring, "get_keyring", fail.Keyring)
