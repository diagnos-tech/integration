"""🇺🇸 One module per command group (`login`, `status`, `patients`, `exams`, `files`, `session`, `groups`).

Every command function is ~10-30 lines: parse flags, call one or two SDK
methods, hand the result to `diagnos_cli.render`. No business logic lives
here — see `CONVENTIONS.md`.

🇧🇷 Um módulo por grupo de comando (`login`, `status`, `patients`, `exams`,
`files`, `session`, `groups`).

Toda função de comando tem ~10-30 linhas: interpreta flags, chama um ou
dois métodos do SDK, entrega o resultado a `diagnos_cli.render`. Nenhuma
lógica de negócio mora aqui — ver `CONVENTIONS.md`.
"""

from __future__ import annotations
