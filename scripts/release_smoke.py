"""🇺🇸 What a freshly built wheel has to prove on its own platform, installed alone: base, then every layer.

The package workflow installs each wheel twice, with nothing from this
repository but this file, on the platform it was built for:

- `base` — `pip install diagnos` alone: no dependency came along, the four
  base commands answer, and the layers explain how to install themselves
  instead of failing with a traceback;
- `full` — `diagnos[sdk,cli,api]`: importing the SDK loads the Rust enclave
  and `memory_status()` says what it guarantees on this machine, `diagnos`
  is the full command line, and `diagnos-api` starts its parser.

A wheel linked for the wrong platform, or one that left a file or an extra
out, fails here instead of on someone's machine.

🇧🇷 O que um wheel recém-construído precisa provar na própria plataforma, instalado sozinho: a base, depois toda camada.

O workflow de pacote instala cada wheel duas vezes, sem nada deste
repositório além deste arquivo, na plataforma para a qual foi construído:

- `base` — `pip install diagnos` sozinho: nenhuma dependência veio junto,
  os quatro comandos da base respondem, e as camadas explicam como se
  instalar em vez de falhar com um traceback;
- `full` — `diagnos[sdk,cli,api]`: importar o SDK carrega o enclave Rust e
  `memory_status()` diz o que ele garante nesta máquina, o `diagnos` é a
  linha de comando completa, e o `diagnos-api` sobe o parser dele.

Um wheel linkado para a plataforma errada, ou que deixou um arquivo ou um
extra de fora, falha aqui em vez de na máquina de alguém.
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
    """🇺🇸 One console script of the installed wheel, captured. 🇧🇷 Um console script do wheel instalado, capturado."""
    program = shutil.which(argv[0])
    assert program is not None, f"{argv[0]} is not installed · não está instalado"
    return subprocess.run([program, *argv[1:]], capture_output=True, text=True, check=False)  # noqa: S603


def base() -> None:
    """🇺🇸 The bare install: zero dependencies, four commands, friendly layers. 🇧🇷 A instalação pura."""
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
        raise AssertionError("the SDK loaded without its extra · o SDK carregou sem o extra")
    print(f"base · diagnos {diagnos.__version__} · CPython {platform.python_version()} · {sys.platform}")


def full() -> None:
    """🇺🇸 Every layer: the enclave loads, both commands answer.

    🇧🇷 Toda camada: o enclave carrega, os dois comandos respondem.
    """
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
    """🇺🇸 `base` or `full`; an `AssertionError` (exit 1) names what is wrong. 🇧🇷 `base` ou `full`."""
    checks = {"base": base, "full": full}
    if len(argv) != 1 or argv[0] not in checks:
        print("usage · uso: release_smoke.py base|full", file=sys.stderr)
        return 2
    checks[argv[0]]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
