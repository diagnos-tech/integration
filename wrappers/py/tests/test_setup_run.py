"""🇺🇸 How a plan runs: shown first, confirmed once (default no), stopped at the first failure.

🇧🇷 Como um plano roda: mostrado antes, confirmado uma vez (padrão não), parado na primeira falha.
"""

from __future__ import annotations

import io

import pytest

from diagnos._wrapper.exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from diagnos._wrapper.output import Output
from diagnos._wrapper.setup.run import Plan, Step, carry_out, command, shown

from conftest import Programs


class _Keyboard(io.StringIO):
    """🇺🇸 Typed input on a terminal. 🇧🇷 Entrada digitada num terminal."""

    def isatty(self) -> bool:
        """🇺🇸 Always a terminal. 🇧🇷 Sempre um terminal."""
        return True


def _plan() -> Plan:
    """🇺🇸 Two commands and a next step. 🇧🇷 Dois comandos e um próximo passo."""
    return Plan(
        "Title",
        (command("first", ("/usr/bin/uv", "pip", "install", "a b")), command("second", ("/usr/bin/uv", "sync"))),
        ("next step",),
    )


def test_shown_is_what_a_person_would_type() -> None:
    """🇺🇸 The program by its bare name, arguments quoted. 🇧🇷 O programa pelo nome, argumentos entre aspas."""
    assert shown(("/usr/local/bin/uv", "add", "diagnos[sdk]>=1")) == "uv add 'diagnos[sdk]>=1'"


def test_dry_run_prints_the_plan_and_runs_nothing(programs: Programs, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Every step and its command, nothing executed. 🇧🇷 Todo passo e seu comando, nada executado."""
    assert carry_out(_plan(), Output(), assume_yes=False, dry_run=True, stdin=io.StringIO()) == EXIT_OK
    text = capsys.readouterr().out
    assert "1. first" in text and "$ uv pip install 'a b'" in text and programs.calls == []


def test_no_terminal_and_no_yes_runs_nothing(programs: Programs, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 A script must not mistake it for success. 🇧🇷 Um script não pode confundir isso com sucesso."""
    assert carry_out(_plan(), Output(), assume_yes=False, dry_run=False, stdin=io.StringIO()) == EXIT_USAGE
    assert "--yes" in capsys.readouterr().err and programs.calls == []


@pytest.mark.parametrize("answer", ["\n", "n\n", "nope\n", ""])
def test_anything_but_yes_declines(answer: str, programs: Programs, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 Enter alone, `n`, gibberish or end of input: nothing runs.

    🇧🇷 Enter, `n`, lixo ou fim da entrada: nada roda.
    """
    assert carry_out(_plan(), Output(), assume_yes=False, dry_run=False, stdin=_Keyboard(answer)) == EXIT_FAILED
    assert "[y/N]" in capsys.readouterr().out and programs.calls == []


@pytest.mark.parametrize("answer", ["y\n", "YES\n", "s\n", "sim\n"])
def test_yes_in_either_language_runs_every_step(
    answer: str, programs: Programs, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Both steps, in order, then what to do next. 🇧🇷 Os dois passos, em ordem, e o que fazer depois."""
    assert carry_out(_plan(), Output(), assume_yes=False, dry_run=False, stdin=_Keyboard(answer)) == EXIT_OK
    assert programs.calls == [["/usr/bin/uv", "pip", "install", "a b"], ["/usr/bin/uv", "sync"]]
    assert capsys.readouterr().out.rstrip().endswith("next step")


def test_the_first_failure_stops_the_plan(programs: Programs, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `EXIT_FAILED`, never the tool's own code; the rest does not run.

    🇧🇷 `EXIT_FAILED`, nunca o código da ferramenta.
    """
    programs.answer("uv", "pip", returncode=2)
    assert carry_out(_plan(), Output(), assume_yes=True, dry_run=False, stdin=io.StringIO()) == EXIT_FAILED
    assert programs.calls == [["/usr/bin/uv", "pip", "install", "a b"]]
    assert "Step 1 failed (exit 2)" in capsys.readouterr().err


def test_a_plan_without_next_steps_ends_at_done(capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 No empty "Next" heading. 🇧🇷 Sem título "Próximo" vazio."""
    plan = Plan("Title", (Step("only", "true", lambda _out: EXIT_OK),))
    assert carry_out(plan, Output(), assume_yes=True, dry_run=False, stdin=io.StringIO()) == EXIT_OK
    assert "Next" not in capsys.readouterr().out
