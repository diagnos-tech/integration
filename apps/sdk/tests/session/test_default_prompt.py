"""`default_prompt`: the plain-text approval prompt printed to `stderr` when no `on_prompt` is given.

Split out of `test_manager.py` on purpose: `default_prompt` is a
module-level function, not a `SessionManager` method — a different unit
under test, and one small enough to earn its own file rather than pad an
already-large one.
"""

from __future__ import annotations

import pytest

from diagnos.session.enrollment import EnrollmentPrompt
from diagnos.session.manager import default_prompt


def test_default_prompt_prints_the_link_and_spaced_code_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """`default_prompt` writes the approval URL and the code, digits spaced, to `stderr`."""
    prompt = EnrollmentPrompt(
        enrollment_id="enr_1", approval_url="https://vault.example.test/approve/enr_1", code="123456", expires_at=42
    )

    default_prompt(prompt)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "https://vault.example.test/approve/enr_1" in captured.err
    assert "1 2 3 4 5 6" in captured.err
    assert "42" in captured.err
