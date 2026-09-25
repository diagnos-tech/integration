"""🇺🇸 `diagnos-cli` — the `diagnos` command line, a thin shell over the `diagnos` SDK.

Every module under this package imports only `diagnos` (never
`diagnos.transport`, `diagnos.crypto`, `diagnos.session.*`) — see
`CONVENTIONS.md`. Business logic (encryption, signing, retries) lives in the
SDK; this package only parses arguments and renders what the SDK returns.

🇧🇷 `diagnos-cli` — a linha de comando `diagnos`, uma casca fina sobre o SDK `diagnos`.

Todo módulo deste pacote importa só `diagnos` (nunca `diagnos.transport`,
`diagnos.crypto`, `diagnos.session.*`) — ver `CONVENTIONS.md`. A lógica de
negócio (cifragem, assinatura, retentativas) mora no SDK; este pacote só
interpreta argumentos e renderiza o que o SDK devolve.
"""

from __future__ import annotations

from ._version import __version__ as __version__
