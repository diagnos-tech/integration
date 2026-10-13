"""🇺🇸 `diagnos docs` and `diagnos version`: the three sites, and this installation at a glance.

🇧🇷 `diagnos docs` e `diagnos version`: os três sites, e esta instalação de relance.
"""

from __future__ import annotations

import json

import pytest

from diagnos._wrapper.docs import LINKS, docs
from diagnos._wrapper.exit_codes import EXIT_OK, EXIT_USAGE
from diagnos._wrapper.output import Output
from diagnos._wrapper.version import installation, version

from conftest import Packages


def test_docs_lists_the_three_sites(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Name, URL and what is there, one per line. 🇧🇷 Nome, URL e o que há lá, um por linha."""
    assert docs(None, open_browser=False, out=Output()) == EXIT_OK
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[-1] for line in lines] != [] and len(lines) == 3
    assert all(link.url in text for link, text in zip(LINKS, lines, strict=True))


def test_docs_with_a_topic_prints_the_bare_url(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Composable: `open "$(diagnos docs dev)"`. 🇧🇷 Para compor: `open "$(diagnos docs dev)"`."""
    docs("dev", open_browser=False, out=Output())
    assert capsys.readouterr().out == "https://dev.diagnos.health\n"


def test_docs_json_is_keyed_by_topic(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 The shape every wrapper prints. 🇧🇷 O formato que todo wrapper imprime."""
    docs("trust", open_browser=False, out=Output(json_output=True))
    assert json.loads(capsys.readouterr().out) == {
        "trust": {"name": "Trust Center", "url": "https://trust.diagnos.health"}
    }


def test_docs_open_hands_the_url_to_the_browser(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Opened when possible, printed when not. 🇧🇷 Aberta quando possível, impressa quando não."""
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    assert docs("help", open_browser=True, out=Output()) == EXIT_OK and opened == ["https://docs.diagnos.health"]
    monkeypatch.setattr("webbrowser.open", lambda _url: False)
    assert docs("help", open_browser=True, out=Output()) == EXIT_OK
    assert "https://docs.diagnos.health" in capsys.readouterr().err


def test_docs_open_needs_a_topic(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Which of the three to open is not a guess. 🇧🇷 Qual dos três abrir não é um palpite."""
    assert docs(None, open_browser=True, out=Output()) == EXIT_USAGE
    assert "help, dev, trust" in capsys.readouterr().err


def test_version_shows_what_is_missing_and_how_to_add_it(
    packages: Packages, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Installed extras plain, missing ones with their install command.

    🇧🇷 Extras instalados simples, ausentes com o comando.
    """
    packages.present = {"httpx", "pydantic"}
    assert version(out=Output()) == EXIT_OK
    text = capsys.readouterr().out
    assert text.startswith("diagnos ") and "  sdk  " in text
    assert "diagnos setup cli" in text and 'pip install "diagnos[openbao]"' in text


def test_version_json_is_the_installation(packages: Packages, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Machine-readable, for bug reports. 🇧🇷 Legível por máquina, para relatos de bug."""
    version(out=Output(json_output=True))
    printed = json.loads(capsys.readouterr().out)
    assert printed == installation() and printed["extras"]["sdk"] is False
    assert set(printed) == {"diagnos", "python", "implementation", "executable", "platform", "extras"}


def test_version_of_an_uninstalled_tree_skips_the_extras(
    packages: Packages, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 No metadata, no extras section. 🇧🇷 Sem metadados, sem seção de extras."""
    packages.diagnos = None
    version(out=Output())
    assert "Extras" not in capsys.readouterr().out
