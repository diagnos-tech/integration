"""Runs every ```` ```python ```` block of the published docs, so no example can rot.

The convention, stated once (`docs/README.md` explains it to writers):

- every block fenced as ```` ```python ```` on a page of `docs/site.json`
  (both languages) runs, top to bottom, in one namespace per page — like a
  notebook, a later block may use `vault` or `patient` from an earlier one;
- ```` ```python no-run ```` opts one block out (a fragment, a signature,
  code that needs a real OpenBao); any other language never runs;
- each page gets a fresh `sandbox` (the real SDK against an in-memory
  vault) and its own temporary working directory; output is captured and
  only shown when a block fails.

A failure is reported at the Markdown line that raised: the block is
compiled with its body shifted to the line it has in the file.
"""

from __future__ import annotations

import contextlib
import io
import traceback
from dataclasses import dataclass
from pathlib import Path

from .markdown import Fence, fences
from .sandbox import sandbox

RUNNABLE = "python"
SKIP_FLAG = "no-run"


@dataclass(frozen=True)
class Outcome:
    """How many blocks of one file ran, and the problem lines of the ones that failed."""

    ran: int
    problems: list[str]


def runnable(text: str) -> list[Fence]:
    """Returns the blocks of a page that run: `python` ones not opted out with `no-run`."""
    return [fence for fence in fences(text) if fence.language == RUNNABLE and SKIP_FLAG not in fence.flags]


def _failure(where: str, fence: Fence, error: BaseException, output: str) -> str:
    """Returns `file:line: snippet failed — Error: message`, pointing at the deepest frame inside the Markdown file."""
    line = fence.line
    for frame in traceback.extract_tb(error.__traceback__):
        if frame.filename == where and frame.lineno is not None:
            line = frame.lineno
    detail = f"{type(error).__name__}: {error}".strip()
    tail = "\n".join(f"    | {row}" for row in output.strip().splitlines()[-8:])
    return f"{where}:{line}: snippet failed — {detail}" + (f"\n{tail}" if tail else "")


def run_file(path: Path, root: Path) -> Outcome:
    """Runs one page's blocks in order, in one sandbox; stops that page at its first failure.

    A later block usually depends on an earlier one, so going on after a
    failure would only report the same root cause again.

    Args:
        path: The Markdown file, under `root`.
        root: The repository root, which the reported file names are relative to.

    Returns:
        How many blocks ran (the failing one included) and the problem line of the failure, if any.
    """
    blocks = runnable(path.read_text(encoding="utf-8"))
    if not blocks:
        return Outcome(ran=0, problems=[])
    where = str(path.relative_to(root))
    namespace: dict[str, object] = {"__name__": "__docs__"}
    output = io.StringIO()
    with sandbox(), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        for ran, fence in enumerate(blocks):
            try:
                # `dont_inherit`: this module's `from __future__` must not leak into the reader's code.
                code = compile("\n" * (fence.line - 1) + fence.body, where, "exec", dont_inherit=True)
                exec(code, namespace)  # noqa: S102 — running the docs' own examples is the point
            except (Exception, SystemExit) as error:
                return Outcome(ran=ran + 1, problems=[_failure(where, fence, error, output.getvalue())])
    return Outcome(ran=len(blocks), problems=[])
