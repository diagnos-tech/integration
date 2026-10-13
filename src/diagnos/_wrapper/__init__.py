"""🇺🇸 The base of `diagnos`: four commands that need nothing but the standard library.

`docs`, `version`, `setup` and `help` are the whole command line of
`pip install diagnos`, and stay available — through the full CLI's own
parser — once `diagnos[cli]` is in. They are also the contract the wrappers
in other languages implement (`wrappers/README.md`), so a TypeScript or Go
developer gets the same first five minutes as a Python one. Nothing in this
package may import the SDK, the CLI or the API: it must run where none of
their dependencies exist.

🇧🇷 A base do `diagnos`: quatro comandos que não precisam de nada além da biblioteca padrão.

`docs`, `version`, `setup` e `help` são a linha de comando inteira do
`pip install diagnos`, e continuam disponíveis — pelo próprio parser da CLI
completa — quando o `diagnos[cli]` entra. São também o contrato que os
wrappers em outras linguagens implementam (`wrappers/README.pt-BR.md`), para
quem programa em TypeScript ou Go ter os mesmos primeiros cinco minutos de
quem programa em Python. Nada neste pacote pode importar o SDK, a CLI ou a
API: ele precisa rodar onde nenhuma das dependências deles existe.
"""

from __future__ import annotations

from .app import main

__all__ = ["main"]
