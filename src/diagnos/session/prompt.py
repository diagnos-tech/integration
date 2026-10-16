"""🇺🇸 `default_prompt`: how the legacy `apikey-` token's approval link and code reach a person, in plain text.

Only the legacy token still needs a human to approve a session; a service
account token opens its own (`token_session.py`).

🇧🇷 `default_prompt`: como o link e o código de aprovação do token legado `apikey-` chegam a uma pessoa, em texto puro.

Só o token legado ainda precisa de uma pessoa aprovando a sessão; um token de
conta de serviço abre a própria (`token_session.py`).
"""

from __future__ import annotations

import sys

from diagnos.session.enrollment import EnrollmentPrompt


def default_prompt(prompt: EnrollmentPrompt) -> None:
    """🇺🇸 Prints the approval link and code to `stderr`, in English then Portuguese (legacy `apikey-` token only).

    No color, no animation: this has to render correctly in a plain CI log
    or a piped process just as well as an interactive terminal, and the
    person approving needs to be able to read the code back accurately —
    spacing the digits out is the only concession to legibility.

    🇧🇷 Imprime o link de aprovação e o código em `stderr`, em inglês e depois português (só o token legado).

    Sem cor, sem animação: isto precisa renderizar certo tanto num log de CI
    puro ou processo com saída redirecionada quanto num terminal
    interativo, e quem aprova precisa conseguir ler o código de volta com
    precisão — espaçar os dígitos é a única concessão à legibilidade.
    """
    spaced_code = " ".join(prompt.code)
    lines = [
        "",
        "diagnos SDK — enrollment approval needed · aprovação de enrollment necessária",
        "",
        "Open this link to approve · Abra este link para aprovar:",
        f"  {prompt.approval_url}",
        "",
        "Code to type · Código para digitar:",
        f"  {spaced_code}",
        "",
        f"Expires at (unix seconds) · Expira em (segundos unix): {prompt.expires_at}",
        "",
    ]
    print("\n".join(lines), file=sys.stderr)
