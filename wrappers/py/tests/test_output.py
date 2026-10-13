"""🇺🇸 `_wrapper.output`: color only where it renders, aligned tables, JSON as is.

🇧🇷 `_wrapper.output`: cor só onde ela renderiza, tabelas alinhadas, JSON como é.
"""

from __future__ import annotations

import io

import pytest

from diagnos._wrapper.output import Output, color_wanted, table


class _Terminal(io.StringIO):
    """🇺🇸 A stream that says it is a terminal. 🇧🇷 Um stream que diz ser um terminal."""

    def isatty(self) -> bool:
        """🇺🇸 Always a terminal. 🇧🇷 Sempre um terminal."""
        return True


@pytest.mark.parametrize(
    ("env", "platform", "expected"),
    [
        ({}, "linux", True),
        ({"NO_COLOR": "1"}, "linux", False),
        ({"NO_COLOR": ""}, "linux", True),
        ({"TERM": "dumb"}, "linux", False),
        ({}, "win32", False),
        ({"WT_SESSION": "x"}, "win32", True),
        ({"TERM": "xterm"}, "win32", True),
    ],
)
def test_color_follows_the_usual_conventions(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], platform: str, expected: bool
) -> None:
    """🇺🇸 `NO_COLOR` (non-empty), `TERM=dumb`, legacy Windows consoles.

    🇧🇷 `NO_COLOR` (não vazia), `TERM=dumb`, Windows legado.
    """
    monkeypatch.setattr("sys.platform", platform)
    assert color_wanted(_Terminal(), env) is expected


def test_no_color_off_a_terminal() -> None:
    """🇺🇸 A pipe or a file never gets escape codes. 🇧🇷 Um pipe ou arquivo nunca recebe códigos de escape."""
    assert not color_wanted(io.StringIO(), {})


def test_terminal_output_respects_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `--no-color` wins over a capable terminal. 🇧🇷 O `--no-color` vence um terminal capaz."""
    monkeypatch.setattr("sys.stdout", _Terminal())
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    assert Output.terminal().color and not Output.terminal(no_color=True).color
    assert Output.terminal(json_output=True).json_output


def test_style_wraps_only_with_color() -> None:
    """🇺🇸 Plain text stays plain. 🇧🇷 Texto simples continua simples."""
    assert Output(color=False).style("x", "bold") == "x"
    assert Output(color=True).style("x") == "x"
    assert Output(color=True).style("x", "bold", "red") == "\x1b[1;31mx\x1b[0m"


def test_lines_errors_and_json_go_to_their_streams() -> None:
    """🇺🇸 Results on stdout, problems on stderr. 🇧🇷 Resultados no stdout, problemas no stderr."""
    stdout, stderr = io.StringIO(), io.StringIO()
    out = Output(stdout, stderr)
    out.line("a")
    out.error("b")
    out.data({"ç": 1})
    assert stdout.getvalue() == 'a\n{\n  "ç": 1\n}\n' and stderr.getvalue() == "b\n"


def test_table_aligns_every_column_but_the_last() -> None:
    """🇺🇸 Ragged last column, no trailing spaces. 🇧🇷 Última coluna solta, sem espaços no fim."""
    assert table([("a", "1", "x"), ("bbb", "22", "")]) == ["  a    1   x", "  bbb  22"]
    assert table([]) == []
