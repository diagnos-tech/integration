"""🇺🇸 The one question a freshly built wheel has to answer: installed alone, does the enclave load here?

The release workflow installs each SDK wheel, with its real dependencies
and nothing from this repository, on the platform it was built for, and
runs this file. Importing `diagnos` loads the Rust extension;
`memory_status()` calls into it and says what it guarantees on this
machine. A wheel that was linked for the wrong platform, or that left a
file out, fails here instead of on someone's server.

🇧🇷 A única pergunta que um wheel recém-construído precisa responder: instalado sozinho, o enclave carrega aqui?

O workflow de release instala cada wheel do SDK, com as dependências de
verdade e nada deste repositório, na plataforma para a qual foi construído,
e roda este arquivo. Importar `diagnos` carrega a extensão Rust;
`memory_status()` chama dentro dela e diz o que ela garante nesta máquina.
Um wheel linkado para a plataforma errada, ou que deixou um arquivo de fora,
falha aqui em vez de no servidor de alguém.
"""

from __future__ import annotations

import platform
import sys
from importlib.metadata import version

import diagnos


def main() -> int:
    """🇺🇸 Prints what was loaded; exit code 1 if the package and its metadata disagree on the version.

    🇧🇷 Imprime o que foi carregado; código de saída 1 se o pacote e os metadados divergem na versão.
    """
    status = diagnos.memory_status()
    print(
        f"diagnos {diagnos.__version__} · CPython {platform.python_version()} · {sys.platform} {platform.machine()}"
        f" · enclave: {status['backend']}, lock policy {status['lock_policy']}"
    )
    return 0 if diagnos.__version__ == version("diagnos") else 1


if __name__ == "__main__":
    sys.exit(main())
