"""🇺🇸 `diagnos --version` prints the CLI's own version and exits `0`.

🇧🇷 `diagnos --version` imprime a versão da própria CLI e sai com `0`.
"""

from __future__ import annotations

from diagnos_cli import __version__
from diagnos_cli.main import typer_app
from typer.testing import CliRunner


def test_version_flag(runner: CliRunner) -> None:
    """🇺🇸 `--version` never touches `build_client` — it exits before any command body runs.

    🇧🇷 `--version` nunca toca `build_client` — sai antes de qualquer corpo de comando rodar.
    """
    result = runner.invoke(typer_app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
