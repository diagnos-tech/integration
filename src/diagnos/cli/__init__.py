"""🇺🇸 `diagnos.cli` — the full `diagnos` command line (`diagnos[cli]`), a thin shell over the SDK.

Every module under this package imports only `diagnos` (never
`diagnos.transport`, `diagnos.crypto`, `diagnos.session.*`) — see
`CONTRIBUTING.md`. Business logic (encryption, signing, retries) lives in
the SDK; this package only parses arguments and renders what the SDK
returns. Importing it without the `cli` extra raises `MissingExtraError`
with the command that adds it.

🇧🇷 `diagnos.cli` — a linha de comando `diagnos` completa (`diagnos[cli]`), uma casca fina sobre o SDK.

Todo módulo deste pacote importa só `diagnos` (nunca `diagnos.transport`,
`diagnos.crypto`, `diagnos.session.*`) — ver `CONTRIBUTING.pt-BR.md`. A
lógica de negócio (cifragem, assinatura, retentativas) mora no SDK; este
pacote só interpreta argumentos e renderiza o que o SDK devolve. Importá-lo
sem o extra `cli` lança `MissingExtraError` com o comando que o soma.
"""

from __future__ import annotations

from diagnos._extras import require

require("cli", "diagnos.cli")
