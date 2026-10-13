"""🇺🇸 The base's exit codes — the same four every language wrapper returns (`wrappers/contract.json`).

`EXIT_UNAVAILABLE` borrows `EX_UNAVAILABLE` from BSD `sysexits.h`: something
this command needs (`uv`, Docker, an extra) is not installed. It sits far
from the full CLI's `1`–`7`, so a script can tell "not installed here" from
any vault error.

🇧🇷 Os códigos de saída da base — os mesmos quatro que todo wrapper de linguagem devolve (`wrappers/contract.json`).

`EXIT_UNAVAILABLE` empresta o `EX_UNAVAILABLE` do `sysexits.h` do BSD: algo
de que este comando precisa (`uv`, Docker, um extra) não está instalado. Fica
longe dos `1`–`7` da CLI completa, para um script distinguir "não instalado
aqui" de qualquer erro do cofre.
"""

from __future__ import annotations

from typing import Final

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_USAGE: Final = 2
EXIT_UNAVAILABLE: Final = 69
