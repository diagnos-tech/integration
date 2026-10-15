"""🇺🇸 Every `examples/*/main.py` runs, end to end, against the docs sandbox (the real SDK, an in-memory vault).

The end-to-end harness proves the examples against a real server; this is the
fast guard that runs in `make test`: an example that stops working with the SDK
fails here, and what it must print (`stdout_includes` of its `example.json`) is
checked too.

🇧🇷 Todo `examples/*/main.py` roda, de ponta a ponta, contra o sandbox da doc (o SDK de verdade, um cofre em memória).

O harness ponta a ponta prova os exemplos contra um server de verdade; este é
o guarda rápido que roda no `make test`: um exemplo que deixa de funcionar com
o SDK falha aqui, e o que ele deve imprimir (`stdout_includes` do `example.json`)
também é conferido.
"""

from __future__ import annotations

import contextlib
import io
import json
import runpy
from pathlib import Path

import pytest

from scripts.docs.output import REPO_ROOT
from scripts.docs.sandbox import sandbox

EXAMPLES = sorted(path for path in (REPO_ROOT / "examples").iterdir() if (path / "main.py").is_file())


@pytest.mark.parametrize("folder", EXAMPLES, ids=lambda folder: folder.name)
def test_example_runs_and_prints_what_it_promises(folder: Path) -> None:
    """🇺🇸 Exit code 0 and every `stdout_includes` line. 🇧🇷 Código de saída 0 e toda linha de `stdout_includes`."""
    manifest = folder / "example.json"
    promised: list[str] = (
        json.loads(manifest.read_text(encoding="utf-8")).get("stdout_includes", []) if manifest.exists() else []
    )
    stdout, stderr = io.StringIO(), io.StringIO()
    with sandbox(), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        with pytest.raises(SystemExit) as finished:
            runpy.run_path(str(folder / "main.py"), run_name="__main__")
    assert finished.value.code == 0, stderr.getvalue()
    assert [line for line in promised if line not in stdout.getvalue()] == []
