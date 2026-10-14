"""What a freshly built wheel has to prove on its own platform, installed alone: base, then every layer.

The package workflow installs each wheel twice, with nothing from this repository but this file, on the platform it
was built for:

- `base`: `pip install diagnos` alone. No dependency came along, the four base commands answer, and the layers explain
  how to install themselves instead of failing with a traceback;
- `full`: `diagnos[sdk,cli,api]`. Importing the SDK loads the Rust enclave and `memory_status()` says what it
  guarantees on this machine, `diagnos` is the full command line, and `diagnos-api` starts its parser.

A wheel linked for the wrong platform, or one that left a file or an extra out, fails here instead of on someone's
machine.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from importlib.metadata import version

EXIT_UNAVAILABLE = 69


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    """Runs one console script of the installed wheel and captures its output."""
    program = shutil.which(argv[0])
    assert program is not None, f"{argv[0]} is not installed"
    return subprocess.run([program, *argv[1:]], capture_output=True, text=True, check=False)  # noqa: S603


def base() -> None:
    """Checks the bare install: zero dependencies, four commands, friendly layers."""
    import diagnos

    report = json.loads(_run("diagnos", "version", "--json").stdout)
    assert report["diagnos"] == diagnos.__version__ == version("diagnos"), report
    assert not any(report["extras"].values()), report["extras"]
    assert _run("diagnos", "docs", "dev").stdout.strip() == "https://dev.diagnos.health"
    assert _run("diagnos", "login").returncode == EXIT_UNAVAILABLE
    assert _run("diagnos-api").returncode == EXIT_UNAVAILABLE
    try:
        diagnos.Diagnos  # noqa: B018 — the access itself is the test
    except diagnos.MissingExtraError:
        pass
    else:
        raise AssertionError("the SDK loaded without its extra")
    print(f"base · diagnos {diagnos.__version__} · CPython {platform.python_version()} · {sys.platform}")


def full() -> None:
    """Checks every layer: the enclave loads and both commands answer."""
    import diagnos

    status = diagnos.memory_status()
    assert _run("diagnos", "--help").returncode == 0
    assert "login" in _run("diagnos", "--help").stdout
    assert _run("diagnos-api", "--help").returncode == 0
    print(
        f"full · diagnos {diagnos.__version__} · CPython {platform.python_version()} · {sys.platform} "
        f"{platform.machine()} · enclave: {status['backend']}, lock policy {status['lock_policy']}"
    )


def main(argv: list[str]) -> int:
    """Runs the `base` or `full` check named in `argv`.

    Args:
        argv: The command-line arguments after the program name: `base` or `full`.

    Returns:
        The process exit code: 0 on success, 2 on a usage error. A failed check raises `AssertionError`, which exits
        with status 1 and names what is wrong.
    """
    checks = {"base": base, "full": full}
    if len(argv) != 1 or argv[0] not in checks:
        print("usage: release_smoke.py base|full", file=sys.stderr)
        return 2
    checks[argv[0]]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
