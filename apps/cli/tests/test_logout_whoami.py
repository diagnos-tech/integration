"""🇺🇸 `diagnos logout` forgets the stored token; `diagnos whoami` proves the one in use and says where it came from.

🇧🇷 `diagnos logout` esquece o token guardado; `diagnos whoami` prova o que está em uso e diz de onde veio.
"""

from __future__ import annotations

import json

import keyring
import pytest
from typer.testing import CliRunner

from diagnos.cli.main import typer_app

from .conftest import FakeDiagnos, mint_token
from .test_login import VAULT, Platform


def test_logout_deletes_the_token_from_the_keyring(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Removed once, then there is nothing left to remove. 🇧🇷 Removido uma vez, depois não sobra nada."""
    backend = Platform()
    backend.items[("diagnos", VAULT)] = mint_token()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    first = runner.invoke(typer_app, ["logout"])
    assert first.exit_code == 0
    assert "Token removed from" in first.output and "keyring.backends.macOS.Platform" in first.output
    assert backend.items == {}
    second = runner.invoke(typer_app, ["--json", "logout"])
    assert json.loads(second.output) == {"removed_from": [], "agent_stopped": False, "diagnos_token_still_set": False}


def test_logout_names_a_diagnos_token_it_cannot_clear(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 The shell's `DIAGNOS_TOKEN` is not ours to unset — only named. 🇧🇷 O `DIAGNOS_TOKEN` do shell só é citado."""
    monkeypatch.setenv("DIAGNOS_TOKEN", mint_token())
    result = runner.invoke(typer_app, ["logout"])
    assert "No stored token" in result.output
    assert "DIAGNOS_TOKEN is still set in this shell" in result.output
    assert runner.invoke(typer_app, ["--quiet", "logout"]).output == ""


def test_whoami_shows_identity_source_and_groups(runner: CliRunner, patched_build_client: FakeDiagnos) -> None:
    """🇺🇸 The session opened (groups only exist after `unlock`), and the output names where the token came from.

    🇧🇷 A sessão abriu (os grupos só existem depois do `unlock`), e a saída diz de onde o token veio.
    """
    result = runner.invoke(typer_app, ["whoami"])
    assert result.exit_code == 0
    assert patched_build_client.identity in result.output
    assert "hybrid — keyring" in result.output and "sg_oncology" in result.output
    data = json.loads(runner.invoke(typer_app, ["--json", "whoami"]).output)
    assert (data["workspace_id"], data["security_groups"], data["session_expires_at"]) == (
        "ws_1",
        ["sg_oncology"],
        4_000_000_000,
    )
