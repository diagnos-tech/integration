"""🇺🇸 Runnable snippets: one namespace per page, `no-run` honoured, failures pinned to the Markdown line.

🇧🇷 Snippets executáveis: um namespace por página, `no-run` respeitado, falhas presas à linha do Markdown.
"""

from __future__ import annotations

from pathlib import Path

from scripts.docs.snippets import run_file, runnable


def page(tmp_path: Path, text: str) -> Path:
    """🇺🇸 Writes a page into a scratch root. 🇧🇷 Grava uma página numa raiz de rascunho."""
    path = tmp_path / "page.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_blocks_share_a_namespace_and_run_against_the_sandbox(tmp_path: Path) -> None:
    """🇺🇸 A later block sees an earlier one's names; the SDK really works. 🇧🇷 Um bloco vê os nomes do anterior."""
    text = """# P

```python
from diagnos import Diagnos

vault = Diagnos()
```

```python
patient = vault.patients.create({"legal_name": "A", "display_name": "A"}, security_group="sg_oncology")
assert vault.patients.get(patient.id).record.legal_name == "A"
```
"""
    outcome = run_file(page(tmp_path, text), tmp_path)
    assert (outcome.ran, outcome.problems) == (2, [])


def test_no_run_and_other_languages_are_skipped(tmp_path: Path) -> None:
    """🇺🇸 Only plain ```` ```python ```` runs. 🇧🇷 Só ```` ```python ```` puro roda."""
    text = "# P\n\n```python no-run\nraise SystemExit(1)\n```\n\n```py\nraise SystemExit(1)\n```\n"
    assert runnable(text) == []
    assert run_file(page(tmp_path, text), tmp_path).ran == 0


def test_a_failure_points_at_the_markdown_line(tmp_path: Path) -> None:
    """🇺🇸 The problem names the file and the line that raised. 🇧🇷 O problema nomeia o arquivo e a linha que lançou."""
    text = "# P\n\n```python\nx = 1\nraise ValueError('boom')\n```\n\n```python\nprint('never')\n```\n"
    outcome = run_file(page(tmp_path, text), tmp_path)
    assert outcome.ran == 1
    [problem] = outcome.problems
    assert problem.startswith("page.md:5: snippet failed") and "ValueError: boom" in problem


def test_snippets_are_compiled_without_this_modules_future_imports(tmp_path: Path) -> None:
    """🇺🇸 Annotations are evaluated as in the reader's code. 🇧🇷 Anotações são avaliadas como no código de quem lê."""
    text = "# P\n\n```python\ndef f(x: Undefined) -> None: ...\n```\n"
    [problem] = run_file(page(tmp_path, text), tmp_path).problems
    assert "NameError" in problem
